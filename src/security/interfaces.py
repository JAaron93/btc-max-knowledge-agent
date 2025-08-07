from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from .models import SecuritySeverity, SecurityAction
from .prompt_injection_detector import InjectionType, DetectionResult


class ISecurityValidator(Protocol):
    def validate(self, result: DetectionResult) -> bool: ...


class ISecurityMonitor(Protocol):
    def record(self, result: DetectionResult) -> None: ...


class IConfigurationValidator(Protocol):
    def validate(self, config: dict) -> bool: ...


class IRateLimiter(Protocol):
    def allow(self, key: str) -> bool: ...


class ISecurityLogger(Protocol):
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


class IPromptInjectionDetector(Protocol):
    async def detect_injection(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DetectionResult: ...


@dataclass
class SecurityAlertEvent:
    timestamp: float
    session_id: Optional[str]
    request_id: Optional[str]
    source_ip: Optional[str]
    severity: Optional[SecuritySeverity]
    score: float  # Valid range: [0.0, 1.0]
    detected_patterns: List[str]
    injection_type: Optional[InjectionType]
    action_taken: SecurityAction
    input_sha256_16: str
    details: Dict[str, Any]


class ISecurityAlerter(Protocol):
    async def notify(self, event: SecurityAlertEvent) -> None: ...
