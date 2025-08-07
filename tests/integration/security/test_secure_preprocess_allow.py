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
        # kept for backward-compat in constructor signature; no longer used
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
        # retained for test compatibility but no production usage
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
        )


# Per-test spy logger fixture to ensure consistent, isolated capture
from typing import Tuple, Callable, TypedDict

class SpyLogger(TypedDict):
    calls: List[Tuple[str, Dict[str, Any]]]
    log: Callable[[Dict[str, Any], str], None]

@pytest.fixture
def spy_logger() -> SpyLogger:
    calls: List[Tuple[str, Dict[str, Any]]] = []

    # Production signature: _log_attempt(self, payload, level="info")
    def log(payload: Dict[str, Any], level: str = "info") -> None:
        calls.append((level, payload))

    return {"calls": calls, "log": log}


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.security
async def test_allow_low_score_no_detection(
    monkeypatch: pytest.MonkeyPatch,
    spy_logger: "SpyLogger",
) -> None:
    detector = FakeDetector(
        injection_detected=False,
        confidence_score=0.10,
        risk_level=SecuritySeverity.LOW,
        recommended_action=None,
        patterns=[],
        injection_type=None,
    )
    # Spy for _log_attempt using isolated per-test fixture
    pre = SecurePromptPreprocessor(injection_detector=detector)
    monkeypatch.setattr(pre, "_log_attempt", spy_logger["log"])

    text = "Hello, how are you?"
    res = await pre.secure_preprocess(text, context={"request_id": "rid-1"})

    assert res.allowed is True
    assert res.action_taken == SecurityAction.ALLOW
    assert res.sanitized_text is None
    # system_wrapper always present by design (policy wrapper string)
    assert isinstance(res.system_wrapper, str)
    assert len(res.system_wrapper) > 0

    # Logging should have used debug-level for ALLOW
    assert len(spy_logger["calls"]) == 1
    level, payload = spy_logger["calls"][0]
    assert level == "debug"
    # payload schema fields minimal presence
    assert "ts" in payload and "rid" in payload and "sha8" in payload
    assert payload["action"] == "ALLOW"
    assert payload["sanitized"] is False


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.security
async def test_secure_preprocess_allows_and_returns_sanitized_text(
    monkeypatch: pytest.MonkeyPatch,
    spy_logger: "SpyLogger",
) -> None:
    # Arrange
    detector = FakeDetector(score=0.2, neutralized_query="cleaned")
    preprocessor = SecurePromptPreprocessor(detector)
    # Monkeypatch logger for this test to capture (level, payload) tuples
    monkeypatch.setattr(preprocessor, "_log_attempt", spy_logger["log"])
    user_input = "hello world"

    # Act
    result = await preprocessor.secure_preprocess(user_input)

    # Assert
    assert result.allowed is True
    assert result.action_taken == SecurityAction.ALLOW
    assert result.sanitized_text == "cleaned"
    assert result.system_wrapper is None
    # Verify logging similar to the first test
    assert len(spy_logger["calls"]) >= 1
    assert isinstance(spy_logger["calls"][-1], tuple)
    level_last, last_payload = spy_logger["calls"][-1]
    assert level_last in {"debug", "info", "warning", "error"}
    assert isinstance(last_payload, dict)
    assert "score" in last_payload
    assert isinstance(last_payload["score"], float)
    assert 0.0 <= last_payload["score"] <= 1.0
    if "action" in last_payload:
        assert last_payload["action"] in {"ALLOW", "WARN", "BLOCK", "NONE"}


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