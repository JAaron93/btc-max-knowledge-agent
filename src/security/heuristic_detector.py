from __future__ import annotations

from typing import Any, Dict, List, Optional

from .interfaces import IPromptInjectionDetector
from .models import SecurityAction, SecuritySeverity
from .prompt_injection_detector import DetectionResult, InjectionType


class HeuristicDetector(IPromptInjectionDetector):
    """
    Simple, testable heuristic detector extracted to its own module for reuse
    and independent unit testing.

    Behavior is identical to the previous inline detector used within
    prompt_processor.secure_preprocess.
    """

    async def detect_injection(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DetectionResult:
        lowered = (text or "").lower()
        patterns: List[str] = []
        inj_type: Optional[InjectionType] = None
        score = 0.0

        # Check for instruction override patterns
        if "ignore previous instructions" in lowered:
            patterns.append("instruction-override")
            inj_type = InjectionType.INSTRUCTION_OVERRIDE
            score = max(score, 0.9)

        # Check for role confusion patterns
        if "system:" in lowered or "assistant:" in lowered:
            patterns.append("role-confusion")
            if inj_type is None:  # Don't override higher priority type
                inj_type = InjectionType.ROLE_CONFUSION
            score = max(score, 0.6)

        severity = (
            SecuritySeverity.HIGH
            if score >= 0.85
            else (SecuritySeverity.MEDIUM if score >= 0.5 else SecuritySeverity.LOW)
        )
        recommended = (
            SecurityAction.BLOCK
            if score >= 0.85
            else (SecurityAction.WARN if score >= 0.5 else SecurityAction.ALLOW)
        )

        return DetectionResult(
            injection_detected=score > 0.0,
            confidence_score=score,
            detected_patterns=patterns,
            injection_type=inj_type,
            risk_level=severity,
            recommended_action=recommended,
        )
