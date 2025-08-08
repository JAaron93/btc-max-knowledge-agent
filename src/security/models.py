from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Any, Dict


class SecurityAction(Enum):
    ALLOW = auto()
    WARN = auto()
    BLOCK = auto()


class SecuritySeverity(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    ERROR = auto()
    CRITICAL = auto()


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
    # Use default_factory to avoid mutable default pitfalls and None checks
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float = 0.0
    violations: list["Violation"] = field(default_factory=list)
    recommended_action: SecurityAction = SecurityAction.ALLOW
    # Structured details corresponding to entries in `violations` (same order)
    violations_details: list[Dict[str, Any]] = field(default_factory=list)


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


def _sanitize_thresholds(
    low: float, medium: float, high: float
) -> tuple[float, float, float]:
    """Validate thresholds are within [0,1] and ordered low <= medium <= high.

    Raise ValueError if misconfigured instead of silently sorting so callers
    can correct configuration issues explicitly.
    """
    low = max(0.0, min(1.0, float(low)))
    medium = max(0.0, min(1.0, float(medium)))
    high = max(0.0, min(1.0, float(high)))

    if not (low <= medium <= high):
        raise ValueError(
            f"Invalid thresholds order: expected low <= medium <= high "
            f"but got low={low}, medium={medium}, high={high}"
        )
    return low, medium, high


def get_contextual_severity_for_event_type(
    event_type: str | Enum,
) -> SecuritySeverity:
    """Return a default severity per event type using a keyword→severity map.

    Uses exact keyword matches to avoid unintended partial matches.
    Falls back to LOW when no keyword is matched.
    """
    try:
        et_raw = (
            event_type.name if hasattr(event_type, "name") else str(event_type)
        )
    except Exception:
        et_raw = str(event_type)
    et_norm = et_raw.strip().upper()

    keyword_map = {
        "ALERT": SecuritySeverity.HIGH,
        "RESPONSE": SecuritySeverity.MEDIUM,
        "REQUEST": SecuritySeverity.LOW,
    }

    # Exact match first
    if et_norm in keyword_map:
        return keyword_map[et_norm]

    # If an Enum-like composite value is passed (e.g., "SECURITY_ALERT"),
    # prefer prefix token matching to avoid arbitrary substring matches.
    first_token = et_norm.split("_", 1)[0]
    if first_token in keyword_map:
        return keyword_map[first_token]

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
    """Minimal token bucket stub for rate limiting tests expecting exposure."""

    def __init__(self, capacity: int = 10, refill_rate: float = 1.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity

    def try_consume(self, n: int = 1) -> bool:
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


@dataclass
class Violation:
    violation_type: SecurityViolation
    details: Dict[str, Any] = field(default_factory=dict)
