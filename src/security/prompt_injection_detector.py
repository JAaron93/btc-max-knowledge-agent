from __future__ import annotations

from enum import Enum, auto
from .models import DetectionResult, SecurityAction, SecuritySeverity

class PromptInjectionDetector:
    def detect(self, text: str) -> DetectionResult:
        # Minimal heuristic stub
        lowered = (text or '').lower()
        if 'ignore previous instructions' in lowered or 'system prompt' in lowered:
            return DetectionResult(action=SecurityAction.BLOCK, severity=SecuritySeverity.HIGH, reason='prompt-injection')
        return DetectionResult(action=SecurityAction.ALLOW, severity=SecuritySeverity.LOW)

class InjectionType(Enum):
    NONE = auto()
    PROMPT_INJECTION = auto()
