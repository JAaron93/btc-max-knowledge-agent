import pytest
from typing import Any, Dict, List

from src.security.prompt_processor import SecurePromptPreprocessor
from src.security.models import SecurityAction, SecuritySeverity
from src.security.prompt_injection_detector import (
    DetectionResult,
    InjectionType,
)


class FakeDetector:
    def __init__(
        self,
        score: float = 0.2,
        patterns=None,
        neutralized_query: str | None = None,
        # Additional optional knobs to satisfy tests constructing FakeDetector
        injection_detected: bool | None = None,
        confidence_score: float | None = None,
        risk_level: SecuritySeverity | None = None,
        recommended_action: SecurityAction | None = None,
        injection_type=None,
    ):
        # Core fields
        self.score = score
        self.patterns = patterns or []
        self.neutralized_query = neutralized_query
        # Accept extra kwargs used by tests; fall back to sensible defaults
        self._inj_detected = (
            bool(injection_detected)
            if injection_detected is not None
            else score > 0.0
        )
        self._conf_score = (
            float(confidence_score)
            if confidence_score is not None
            else score
        )
        self._risk_level = (
            risk_level if risk_level is not None else SecuritySeverity.LOW
        )
        self._recommended = (
            recommended_action
            if recommended_action is not None
            else SecurityAction.ALLOW
        )
        self._inj_type = injection_type

    async def detect_injection(self, text, context=None):
        return DetectionResult(
            injection_detected=self._inj_detected,
            confidence_score=self._conf_score,
            detected_patterns=self.patterns,
            injection_type=self._inj_type,
            risk_level=self._risk_level,
            recommended_action=self._recommended,
            neutralized_query=self.neutralized_query,
        )


# Spy logger utilities shared by tests in this module
logged_calls: List[Dict[str, Any]] = []


def spy_log(payload: Dict[str, Any]) -> None:
    # Append payload directly; tests must not mutate logged payloads
    # after it has been logged.
    logged_calls.append(payload)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.security
async def test_allow_low_score_no_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = FakeDetector(
        injection_detected=False,
        confidence_score=0.10,
        risk_level=SecuritySeverity.LOW,
        recommended_action=None,
        patterns=[],
        injection_type=None,
    )
    # Spy for _log_attempt level path
    logged_calls: list[dict] = []

    pre = SecurePromptPreprocessor(injection_detector=detector)

    # Keep signature short; ignore override note kept on separate line
    def spy_log(payload: dict) -> None:
        # Append payload directly; tests must not mutate logged payloads
        # after it has been logged.
        logged_calls.append(payload)

    monkeypatch.setattr(pre, "_log_attempt", spy_log)

    text = "Hello, how are you?"
    res = await pre.secure_preprocess(text, context={"request_id": "rid-1"})

    assert res.allowed is True
    assert res.action_taken == SecurityAction.ALLOW
    assert res.sanitized_text is None
    # system_wrapper always present by design (policy wrapper string)
    assert isinstance(res.system_wrapper, str)
    assert len(res.system_wrapper) > 0

    # Logging should have used debug-level for ALLOW
    assert len(logged_calls) == 1
    level, payload = logged_calls[0]
    assert level == "debug"
    # payload schema fields minimal presence
    assert "ts" in payload and "rid" in payload and "sha8" in payload
    assert payload["action"] == "ALLOW"
    assert payload["sanitized"] is False


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.security
async def test_secure_preprocess_allows_and_returns_sanitized_text() -> None:
    # Arrange
    # Reset shared logger buffer to avoid cross-test contamination
    logged_calls.clear()
    detector = FakeDetector(score=0.2, neutralized_query="cleaned")
    # Pass the injection_detector positionally
    preprocessor = SecurePromptPreprocessor(detector)
    user_input = "hello world"

    # Act
    result = await preprocessor.secure_preprocess(user_input)

    # Assert
    assert result.allowed is True
    assert result.action_taken.name == "ALLOW"
    assert result.sanitized_text == "cleaned"
    assert result.system_wrapper is None
    # Verify logging similar to the first test
    assert len(logged_calls) >= 1
    last = logged_calls[-1]
    assert isinstance(last, dict)
    assert "score" in last
    assert isinstance(last["score"], float)
    assert 0.0 <= last["score"] <= 1.0
    # Optional presence-only checks
    if "allowed" in last:
        assert last["allowed"] is True
    if "action" in last:
        assert last["action"] in {"ALLOW", "NONE", "BLOCK"}


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.security
async def test_allow_detector_recommends_allow_overrides() -> None:
    inj_type = getattr(InjectionType, "OTHER", None)
    detector = FakeDetector(
        injection_detected=True,
        confidence_score=0.20,
        risk_level=SecuritySeverity.LOW,
        recommended_action=SecurityAction.ALLOW,
        patterns=["benign-marker"],
        injection_type=inj_type,
    )

    pre = SecurePromptPreprocessor(injection_detector=detector)
    res = await pre.secure_preprocess("some input", context=None)

    # Even when injection_detected is True, recommended ALLOW at low score
    # leads to ALLOW
    assert res.allowed is True
    assert res.action_taken == SecurityAction.ALLOW
    assert res.sanitized_text is None
    assert isinstance(res.system_wrapper, str)
    assert len(res.system_wrapper) > 0