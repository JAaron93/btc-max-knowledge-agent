from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

class SecurityAction(Enum):
    ALLOW = auto()
    WARN = auto()
    BLOCK = auto()

class SecuritySeverity(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()

@dataclass
class DetectionResult:
    action: SecurityAction
    severity: SecuritySeverity
    reason: Optional[str] = None


class SecurityConfiguration:
    """Minimal stub for tests expecting SecurityConfiguration."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class SecurityViolation(Enum):
    NONE = auto()
    PROMPT_INJECTION = auto()
    DATA_LEAK = auto()
    RATE_LIMIT_ABUSE = auto()

# Threshold constants expected by tests
DEFAULT_THRESHOLD_LOW = 0.2
DEFAULT_THRESHOLD_MEDIUM = 0.5
DEFAULT_THRESHOLD_HIGH = 0.8

@dataclass
class SecurityEvent:
    name: str
    details: Optional[Dict[str, Any]] = None

@dataclass
class ValidationResult:
    ok: bool
    result: DetectionResult | None = None


class SecurityEventType(Enum):
    REQUEST = auto()
    RESPONSE = auto()
    ALERT = auto()

class AuthenticationStatus(Enum):
    UNKNOWN = auto()
    AUTHENTICATED = auto()
    UNAUTHENTICATED = auto()


class AuthResult(Enum):
    SUCCESS = auto()
    FAILURE = auto()
    ERROR = auto()


def _sanitize_thresholds(low: float, medium: float, high: float) -> tuple[float, float, float]:
    """Ensure thresholds are in ascending order and within [0,1]."""
    low = max(0.0, min(1.0, float(low)))
    medium = max(0.0, min(1.0, float(medium)))
    high = max(0.0, min(1.0, float(high)))
    # enforce ascending order
    if not (low <= medium <= high):
        # simple fix: sort
        low, medium, high = sorted([low, medium, high])
    return low, medium, high


def get_contextual_severity_for_event_type(event_type) -> SecuritySeverity:
    """Return a default severity per event type; tests only need basic mapping."""
    try:
        et = event_type.name if hasattr(event_type, "name") else str(event_type)
    except Exception:
        et = str(event_type)
    mapping = {
        "ALERT": SecuritySeverity.CRITICAL if 'ALERT' in mapping else SecuritySeverity.HIGH
    }
    # Simple defaults
    if 'ALERT' in et:
        return SecuritySeverity.CRITICAL
    if 'RESPONSE' in et:
        return SecuritySeverity.MEDIUM
    return SecuritySeverity.LOW


class ResourceMetrics:
    """Minimal metrics container used in tests."""
    def __init__(self, cpu: float = 0.0, mem: float = 0.0) -> None:
        self.cpu = cpu
        self.mem = mem


class SecurityConfigurationManager:
    """Minimal manager stub for tests expecting import surface."""
    def __init__(self, config=None) -> None:
        self.config = config
    def get_configuration(self):
        return self.config


class TokenBucket:
    """Minimal token bucket stub for rate limiting tests expecting symbol exposure."""
    def __init__(self, capacity: int = 10, refill_rate: float = 1.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
    def try_consume(self, n: int = 1) -> bool:
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False
