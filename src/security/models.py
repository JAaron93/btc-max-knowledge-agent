"""
Data models and enums for security components.

This module defines all data structures used throughout the security system,
including events, results, configurations, and supporting enums.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union

logger = logging.getLogger(__name__)

# Ensure logging is configured if the application hasn't set it up yet
# This prevents silent defaulting to WARNING level and improves log visibility
# Only configures logging if no handlers exist (respects existing configurations)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO)


# RATE LIMIT DEFAULTS
# Default threshold values for rate limiting context evaluation
# These constants ensure consistency across the codebase and documentation
DEFAULT_THRESHOLD_LOW = 5
DEFAULT_THRESHOLD_HIGH = 50


class SecurityEventType(Enum):
    """
    Enumeration of security event types for classification and filtering.

    Event Types and Their Typical Severity Levels:
    - AUTHENTICATION_FAILURE: ERROR/CRITICAL - Failed login attempts
    - AUTHENTICATION_SUCCESS: INFO - Successful authentication
    - RATE_LIMIT_EXCEEDED: WARNING/ERROR - Rate limiting triggered
    - INPUT_VALIDATION_FAILURE: WARNING/ERROR/CRITICAL - Malicious input detected
    - INPUT_VALIDATION_SUCCESS: INFO - Input validation passed (for monitoring)
    - PROMPT_INJECTION_DETECTED: CRITICAL - AI prompt injection attempt
    - SUSPICIOUS_QUERY_PATTERN: WARNING/ERROR - Unusual query patterns
    - API_ACCESS_DENIED: WARNING/ERROR - Unauthorized API access
    - CONFIGURATION_CHANGE: INFO/WARNING - Security config changes
    - SYSTEM_ERROR: ERROR/CRITICAL - Internal security system errors
    - DATA_EXFILTRATION_ATTEMPT: CRITICAL - Potential data theft
    - RESOURCE_EXHAUSTION: WARNING/ERROR - System resource limits hit
    - UNAUTHORIZED_ACCESS_ATTEMPT: ERROR/CRITICAL - Access control violations
    - REQUEST_SUCCESS: INFO - Normal request completion (for metrics)
    """

    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHENTICATION_SUCCESS = "authentication_success"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INPUT_VALIDATION_FAILURE = "input_validation_failure"
    INPUT_VALIDATION_SUCCESS = "input_validation_success"
    PROMPT_INJECTION_DETECTED = "prompt_injection_detected"
    SUSPICIOUS_QUERY_PATTERN = "suspicious_query_pattern"
    API_ACCESS_DENIED = "api_access_denied"
    CONFIGURATION_CHANGE = "configuration_change"
    SYSTEM_ERROR = "system_error"
    DATA_EXFILTRATION_ATTEMPT = "data_exfiltration_attempt"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNAUTHORIZED_ACCESS_ATTEMPT = "unauthorized_access_attempt"
    REQUEST_SUCCESS = "request_success"


class SecuritySeverity(Enum):
    """Enumeration of security event severity levels for prioritization and alerting."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Utility functions for SecurityEventType (defined after SecuritySeverity to avoid forward references)
def get_default_severity_for_event_type(
    event_type: SecurityEventType,
) -> SecuritySeverity:
    """
    Get the default/baseline severity level for a given event type.

    This function provides recommended default severity levels for different event types
    to ensure consistent handling across the security system. Note that many event types
    can have contextual variations in severity (as documented in SecurityEventType enum),
    but this function returns the baseline/most common severity level.

    For context-specific severity determination, use get_contextual_severity_for_event_type()
    which considers additional factors like frequency, impact, and system state.

    Args:
        event_type: The security event type

    Returns:
        Default SecuritySeverity level (baseline recommendation)

    Examples:
        >>> get_default_severity_for_event_type(SecurityEventType.RATE_LIMIT_EXCEEDED)
        SecuritySeverity.WARNING  # Default, but could be ERROR in high-frequency scenarios

        >>> get_default_severity_for_event_type(SecurityEventType.INPUT_VALIDATION_FAILURE)
        SecuritySeverity.ERROR  # Default, but could be WARNING for minor issues or CRITICAL for injection attempts
    """
    # Default severity mapping - represents the most common/baseline severity for each event type
    # Many events can have higher severity in specific contexts (see SecurityEventType documentation)
    severity_mapping = {
        SecurityEventType.AUTHENTICATION_FAILURE: SecuritySeverity.ERROR,  # Can be CRITICAL for repeated attempts
        SecurityEventType.AUTHENTICATION_SUCCESS: SecuritySeverity.INFO,
        SecurityEventType.RATE_LIMIT_EXCEEDED: SecuritySeverity.WARNING,  # Can be ERROR for severe rate limiting
        SecurityEventType.INPUT_VALIDATION_FAILURE: SecuritySeverity.ERROR,  # Can be WARNING (minor) or CRITICAL (injection)
        SecurityEventType.INPUT_VALIDATION_SUCCESS: SecuritySeverity.INFO,
        SecurityEventType.PROMPT_INJECTION_DETECTED: SecuritySeverity.CRITICAL,
        SecurityEventType.SUSPICIOUS_QUERY_PATTERN: SecuritySeverity.WARNING,  # Can be ERROR for clearly malicious patterns
        SecurityEventType.API_ACCESS_DENIED: SecuritySeverity.ERROR,  # Can be WARNING for legitimate denials
        SecurityEventType.CONFIGURATION_CHANGE: SecuritySeverity.INFO,  # Can be WARNING for security-critical changes
        SecurityEventType.SYSTEM_ERROR: SecuritySeverity.ERROR,  # Can be CRITICAL for system-wide failures
        SecurityEventType.DATA_EXFILTRATION_ATTEMPT: SecuritySeverity.CRITICAL,
        SecurityEventType.RESOURCE_EXHAUSTION: SecuritySeverity.WARNING,  # Can be ERROR for severe exhaustion
        SecurityEventType.UNAUTHORIZED_ACCESS_ATTEMPT: SecuritySeverity.ERROR,  # Can be CRITICAL for privilege escalation
        SecurityEventType.REQUEST_SUCCESS: SecuritySeverity.INFO,
    }
    return severity_mapping.get(event_type, SecuritySeverity.WARNING)


def _sanitize_thresholds(low: Any, high: Any) -> Tuple[float, float]:
    """
    Sanitize and validate threshold values with consistent logging and fallback behavior.

    This helper function applies three key validation rules:
    1. Type and positivity validation - ensures both values are numeric and positive
    2. Fallback to defaults - replaces invalid values with safe defaults
    3. Ordering validation - ensures low < high, resetting both to defaults if violated

    The function mirrors the logging behavior used throughout the security system
    for consistent traceability and debugging support.

    Args:
        low: The low threshold value (any type, will be validated)
        high: The high threshold value (any type, will be validated)

    Returns:
        A tuple of (sanitized_low, sanitized_high) as float values, guaranteed to be:
        - Both positive numbers
        - low < high
        - Safe defaults if input values were invalid

    Examples:
        >>> _sanitize_thresholds(10, 50)
        (10.0, 50.0)

        >>> _sanitize_thresholds("invalid", 50)  # Invalid low
        (5.0, 50.0)

        >>> _sanitize_thresholds(100, 10)  # Invalid ordering
        (5.0, 50.0)

        >>> _sanitize_thresholds(-5, "bad")  # Both invalid
        (5.0, 50.0)

    Note:
        This function logs warnings for all validation failures using the same
        logger messages and levels as the original implementation for consistency.
    """
    sanitized_low = low
    sanitized_high = high

    # Validate high threshold: correct type and positivity
    if not isinstance(high, (int, float)) or high <= 0:
        logger.warning(
            "Invalid threshold_high value in rate limit context: %s (type: %s). Using default: %s",
            high,
            type(high).__name__,
            DEFAULT_THRESHOLD_HIGH,
        )
        sanitized_high = DEFAULT_THRESHOLD_HIGH

    # Validate low threshold: correct type and positivity
    if not isinstance(low, (int, float)) or low <= 0:
        logger.warning(
            "Invalid threshold_low value in rate limit context: %s (type: %s). Using default: %s",
            low,
            type(low).__name__,
            DEFAULT_THRESHOLD_LOW,
        )
        sanitized_low = DEFAULT_THRESHOLD_LOW

    # Validate ordering: low must be less than high
    if sanitized_low >= sanitized_high:
        logger.warning(
            "Invalid threshold relationship: threshold_low (%s) >= threshold_high (%s). Resetting to defaults (%s, %s)",
            sanitized_low,
            sanitized_high,
            DEFAULT_THRESHOLD_LOW,
            DEFAULT_THRESHOLD_HIGH,
        )
        sanitized_low, sanitized_high = DEFAULT_THRESHOLD_LOW, DEFAULT_THRESHOLD_HIGH

    return float(sanitized_low), float(sanitized_high)


def get_contextual_severity_for_event_type(
    event_type: SecurityEventType, context: Optional[Dict[str, Any]] = None
) -> SecuritySeverity:
    """
    Get context-aware severity level for a given event type.

    This function considers additional context factors to determine the appropriate
    severity level, which may differ from the default severity. Context factors
    include frequency, impact level, system state, and threat indicators.

    Args:
        event_type: The security event type
        context: Optional dictionary containing contextual information:
            - 'frequency': Event frequency (e.g., 'high', 'normal', 'low')
            - 'impact': Impact level (e.g., 'high', 'medium', 'low')
            - 'threat_level': Threat assessment (e.g., 'critical', 'high', 'medium', 'low')
            - 'system_state': Current system state (e.g., 'degraded', 'normal')
            - 'user_type': User type (e.g., 'admin', 'regular', 'anonymous')
            - 'attempt_count': Number of attempts/occurrences
            - 'confidence_score': Detection confidence (0.0 to 1.0)

    Returns:
        Context-appropriate SecuritySeverity level

    Examples:
        >>> # High-frequency rate limiting becomes ERROR
        >>> get_contextual_severity_for_event_type(
        ...     SecurityEventType.RATE_LIMIT_EXCEEDED,
        ...     {'frequency': 'high', 'attempt_count': 100}
        ... )
        SecuritySeverity.ERROR

        >>> # High-confidence injection attempt stays CRITICAL
        >>> get_contextual_severity_for_event_type(
        ...     SecurityEventType.INPUT_VALIDATION_FAILURE,
        ...     {'threat_level': 'critical', 'confidence_score': 0.95}
        ... )
        SecuritySeverity.CRITICAL
    """
    if context is None:
        context = {}

    # Start with default severity
    base_severity = get_default_severity_for_event_type(event_type)

    # Context-specific severity adjustments
    if event_type == SecurityEventType.RATE_LIMIT_EXCEEDED:
        frequency = context.get("frequency", "normal")
        attempt_count = context.get("attempt_count", 0)

        threshold_high = context.get(
            "threshold_high", DEFAULT_THRESHOLD_HIGH
        )  # Could come from config
        threshold_low = context.get("threshold_low", DEFAULT_THRESHOLD_LOW)

        threshold_low, threshold_high = _sanitize_thresholds(
            threshold_low, threshold_high
        )

        if frequency == "high" or attempt_count > threshold_high:
            return SecuritySeverity.ERROR
        elif frequency == "low" and attempt_count < threshold_low:
            return SecuritySeverity.INFO

    elif event_type == SecurityEventType.INPUT_VALIDATION_FAILURE:
        threat_level = context.get("threat_level", "medium")
        confidence_score = context.get("confidence_score", 0.5)

        if threat_level == "critical" or confidence_score > 0.9:
            return SecuritySeverity.CRITICAL
        elif threat_level == "low" or confidence_score < 0.3:
            return SecuritySeverity.WARNING

    elif event_type == SecurityEventType.AUTHENTICATION_FAILURE:
        attempt_count = context.get("attempt_count", 1)
        user_type = context.get("user_type", "regular")

        admin_threshold = 3  # Lower threshold for admin accounts
        regular_threshold = 10
        threshold = admin_threshold if user_type == "admin" else regular_threshold
        if attempt_count > threshold:
            return SecuritySeverity.CRITICAL

    elif event_type == SecurityEventType.SUSPICIOUS_QUERY_PATTERN:
        confidence_score = context.get("confidence_score", 0.5)
        threat_level = context.get("threat_level", "medium")

        if confidence_score > 0.8 or threat_level == "high":
            return SecuritySeverity.ERROR

    elif event_type == SecurityEventType.API_ACCESS_DENIED:
        user_type = context.get("user_type", "regular")
        attempt_count = context.get("attempt_count", 1)

        # Escalate for authenticated users being denied (potential privilege escalation)
        if user_type in ["regular", "admin"]:
            return SecuritySeverity.CRITICAL

        # Escalate for repeated anonymous attempts
        if user_type == "anonymous" and attempt_count > 1:
            return SecuritySeverity.ERROR

        # De-escalate for first-time anonymous access denial (legitimate)
        if user_type == "anonymous" and attempt_count == 1:
            return SecuritySeverity.WARNING

    elif event_type == SecurityEventType.CONFIGURATION_CHANGE:
        impact = context.get("impact", "medium")
        user_type = context.get("user_type", "regular")

        if impact == "high" or user_type != "admin":
            return SecuritySeverity.WARNING

    elif event_type == SecurityEventType.SYSTEM_ERROR:
        impact = context.get("impact", "medium")
        system_state = context.get("system_state", "normal")

        if impact == "high" or system_state == "degraded":
            return SecuritySeverity.CRITICAL

    elif event_type == SecurityEventType.RESOURCE_EXHAUSTION:
        impact = context.get("impact", "medium")
        system_state = context.get("system_state", "normal")

        if impact == "high" or system_state == "degraded":
            return SecuritySeverity.ERROR

    elif event_type == SecurityEventType.UNAUTHORIZED_ACCESS_ATTEMPT:
        user_type = context.get("user_type", "regular")
        threat_level = context.get("threat_level", "medium")

        if user_type == "admin" or threat_level == "critical":
            return SecuritySeverity.CRITICAL

    # Return base severity if no context-specific adjustments apply
    return base_severity


def should_event_trigger_alert(event_type: SecurityEventType) -> bool:
    """
    Determine if an event type should trigger alerts.

    Args:
        event_type: The security event type

    Returns:
        True if the event type should trigger alerts
    """
    alert_triggering_events = {
        SecurityEventType.AUTHENTICATION_FAILURE,
        SecurityEventType.RATE_LIMIT_EXCEEDED,
        SecurityEventType.INPUT_VALIDATION_FAILURE,
        SecurityEventType.PROMPT_INJECTION_DETECTED,
        SecurityEventType.SUSPICIOUS_QUERY_PATTERN,
        SecurityEventType.API_ACCESS_DENIED,
        SecurityEventType.SYSTEM_ERROR,
        SecurityEventType.DATA_EXFILTRATION_ATTEMPT,
        SecurityEventType.RESOURCE_EXHAUSTION,
        SecurityEventType.UNAUTHORIZED_ACCESS_ATTEMPT,
    }
    return event_type in alert_triggering_events


class SecurityAction(Enum):
    """Enumeration of recommended security actions for violation remediation."""

    ALLOW = "allow"
    SANITIZE = "sanitize"
    BLOCK = "block"
    RATE_LIMIT = "rate_limit"
    REQUIRE_AUTHENTICATION = "require_authentication"
    LOG_AND_MONITOR = "log_and_monitor"
    ESCALATE = "escalate"
    QUARANTINE = "quarantine"


class AuthenticationStatus(Enum):
    """Enumeration of authentication result statuses."""

    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    EXPIRED_TOKEN = "expired_token"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    ERROR = "error"


class RateLimitStatus(Enum):
    """Enumeration of rate limiting statuses."""

    ALLOWED = "allowed"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class SecurityViolation:
    """
    Represents a specific security violation detected during validation.

    Attributes:
        violation_type: Type of security violation (e.g., "sql_injection", "xss")
        severity: Severity level of the violation
        description: Human-readable description of the violation
        detected_pattern: The specific pattern that triggered the violation
        confidence_score: Confidence level of the detection (0.0 to 1.0)
        location: Where in the input the violation was detected
        suggested_fix: Recommended action to fix the violation
    """

    violation_type: str
    severity: SecuritySeverity
    description: str
    detected_pattern: Optional[str] = None
    confidence_score: float = 0.0
    location: Optional[str] = None
    # Location field documentation:
    # Indicates where in the input the security violation was detected.
    # This field helps pinpoint the exact location of a security issue for debugging
    # and providing specific feedback to users. The format varies depending on the
    # type of input being validated:
    #
    # Common format patterns:
    # - Field names: "query_parameter", "metadata_field", "header_value", "api_key"
    # - Text positions: "line:column" format, e.g., "5:12", "1:45"
    # - JSON paths: JSONPath notation, e.g., "$.query.filters[0].value", "$.metadata.tags[2]"
    # - Query components: "vector_values", "namespace", "filter_expression", "top_k"
    # - HTTP components: "request_body", "query_string", "authorization_header"
    # - Character ranges: "chars:10-25" for specific character positions in text
    #
    # Examples:
    # - "query_parameter" - violation found in main query parameter
    # - "3:15" - violation at line 3, column 15 of input text
    # - "$.filters[0].field" - violation in first filter's field property
    # - "vector_values" - violation in the vector embedding values
    # - "chars:45-67" - violation in characters 45 through 67
    #
    # Set to None when:
    # - Location cannot be determined (e.g., system-wide violations)
    # - Location is not applicable (e.g., rate limiting violations)
    # - Multiple locations are involved (described in violation description instead)
    #
    # This information is used for:
    # - Debugging security issues during development
    # - Providing specific error messages to API users
    # - Security monitoring and pattern analysis
    # - Automated remediation suggestions

    suggested_fix: Optional[str] = None

    def __post_init__(self):
        """Validate confidence score is within valid range."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")


@dataclass
class ValidationResult:
    """Result of input validation operations."""

    is_valid: bool
    confidence_score: float
    violations: List[SecurityViolation] = field(default_factory=list)
    sanitized_input: Optional[str] = None
    recommended_action: SecurityAction = SecurityAction.ALLOW
    processing_time_ms: float = 0.0

    def __post_init__(self):
        """Validate confidence score is within valid range."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")


@dataclass
class DetectionResult:
    """Result of prompt injection detection operations."""

    injection_detected: bool
    confidence_score: float
    detected_patterns: List[str] = field(default_factory=list)
    injection_type: Optional[str] = (
        None  # e.g., "role_confusion", "delimiter_injection"
    )
    risk_level: SecuritySeverity = SecuritySeverity.INFO
    neutralized_query: Optional[str] = None
    recommended_action: SecurityAction = SecurityAction.ALLOW
    processing_time_ms: float = 0.0

    def __post_init__(self):
        """Validate confidence score is within valid range."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")


@dataclass
class AuthResult:
    """Result of authentication operations."""

    status: AuthenticationStatus
    client_id: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    risk_score: float = 0.0

    def __post_init__(self):
        """Validate risk score is within valid range."""
        if not 0.0 <= self.risk_score <= 1.0:
            raise ValueError("Risk score must be between 0.0 and 1.0")


@dataclass
class RateLimitResult:
    """Result of rate limiting checks."""

    status: RateLimitStatus
    remaining_requests: int = 0
    reset_time: Optional[datetime] = None
    retry_after_seconds: Optional[int] = None
    current_usage: float = 0.0  # Current usage as percentage of limit

    def __post_init__(self):
        """Validate current_usage is within valid percentage range."""
        if not 0.0 <= self.current_usage <= 100.0:
            raise ValueError("current_usage must be between 0.0 and 100.0")


@dataclass
class AuthenticationContext:
    """Context information for authenticated clients."""

    client_id: str
    api_key_hash: str
    permissions: List[str] = field(default_factory=list)
    rate_limit_remaining: int = 0
    last_request_time: Optional[datetime] = None
    risk_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate risk score is within valid range."""
        if not 0.0 <= self.risk_score <= 1.0:
            raise ValueError("Risk score must be between 0.0 and 1.0")


@dataclass
class SecurityEvent:
    """Represents a security event for logging and monitoring."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: SecurityEventType = SecurityEventType.SYSTEM_ERROR
    severity: SecuritySeverity = SecuritySeverity.INFO
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    client_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    mitigation_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert security event to dictionary for logging."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "client_id": self.client_id,
            "details": self.details,
            "mitigation_action": self.mitigation_action,
        }


class AnomalyMetrics(TypedDict, total=False):
    """
    Type definition for anomaly metrics dictionary.

    This TypedDict defines the expected structure for metrics stored in anomalies.
    All fields are optional (total=False) to allow for different types of anomalies
    that may not have all metrics available.
    """

    # Performance metrics
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    response_time_ms: float

    # Security metrics
    error_rate_percent: float
    failed_auth_attempts: float
    suspicious_ip_count: float
    query_volume_increase_percent: float
    entropy_threshold: float

    # Network metrics
    active_connections: float
    request_rate_per_minute: float
    bandwidth_usage_mbps: float

    # Threshold comparison values
    threshold_value: float
    current_value: float
    deviation_percent: float


def _create_empty_anomaly_metrics() -> AnomalyMetrics:
    """Create an empty AnomalyMetrics dictionary."""
    return {}


@dataclass
class Anomaly:
    """Represents a detected security anomaly."""

    anomaly_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    anomaly_type: str = "unknown"
    severity: SecuritySeverity = SecuritySeverity.WARNING
    description: str = ""
    metrics: AnomalyMetrics = field(default_factory=_create_empty_anomaly_metrics)
    threshold_exceeded: Optional[str] = None
    recommended_actions: List[str] = field(default_factory=list)


@dataclass
class SecureQuery:
    """Represents a validated and secure query for Pinecone."""

    # Class-level constants for validation limits
    MAX_TOP_K = 50  # Maximum number of results to return (MAX_METADATA_FIELDS limit)
    MAX_QUERY_SIZE = (
        4096  # Maximum query text size in bytes (4KB, MAX_REQUEST_SIZE limit)
    )

    query_text: str
    query_vector: Optional[List[float]] = None
    top_k: int = 10
    namespace: Optional[str] = None
    metadata_filter: Optional[Dict[str, Any]] = None
    include_metadata: bool = True
    include_values: bool = False
    client_id: Optional[str] = None

    def __post_init__(self):
        """Validate query parameters."""
        if self.top_k <= 0 or self.top_k > self.MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {self.MAX_TOP_K}")

        if len(self.query_text.encode("utf-8")) > self.MAX_QUERY_SIZE:
            raise ValueError(
                f"Query text exceeds maximum size of {self.MAX_QUERY_SIZE // 1024}KB"
            )


class PineconeResponse(TypedDict, total=False):
    """
    Type definition for raw Pinecone API response structure.

    This TypedDict defines the expected structure of responses from Pinecone API
    before security validation and filtering. All fields are optional (total=False)
    to accommodate different response types and API versions.
    """

    # Query response fields
    matches: List[Dict[str, Any]]
    namespace: str

    # Usage and metadata
    usage: Dict[str, Any]

    # Vector operations
    vectors: Dict[str, Any]

    # Index operations
    dimension: int
    index_fullness: float
    total_vector_count: int

    # Upsert/delete operations
    upserted_count: int

    # Statistics
    namespaces: Dict[str, Any]

    # Error information (if present)
    error: Dict[str, Any]
    message: str
    code: int


@dataclass
class SecureResponse:
    """Represents a validated and filtered response from Pinecone."""

    matches: List[Dict[str, Any]] = field(default_factory=list)
    namespace: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    filtered_content: List[str] = field(
        default_factory=list
    )  # Content removed for security
    processing_time_ms: float = 0.0


@dataclass
class SecurityConfiguration:
    """Configuration settings for security components."""

    # Input validation limits
    max_query_length: int = 4096  # 4 KB maximum (MAX_REQUEST_SIZE)
    max_metadata_fields: int = 50  # MAX_METADATA_FIELDS
    max_context_tokens: int = 8192  # MAX_CONTEXT_WINDOW
    max_tokens: int = 1000  # MAX_TOKENS

    # Authentication and rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 10  # Token bucket capacity
    rate_limit_refill_rate: float = 1.67  # Tokens per second (100/60)
    auth_cache_validation_timeout_ms: int = 100  # AUTH_CACHE_VALIDATION_TIMEOUT
    auth_remote_fetch_timeout_ms: int = 300  # AUTH_REMOTE_FETCH_TIMEOUT
    api_key_min_length: int = 32
    api_key_max_length: int = 64

    # Prompt injection detection
    injection_detection_threshold: float = 0.8
    injection_accuracy_target: float = 0.95
    sanitization_confidence_threshold: float = 0.7

    # Resource limits
    max_concurrent_per_ip: int = 50  # MAX_CONCURRENT_PER_IP
    max_concurrent_system: int = 200  # MAX_CONCURRENT_SYSTEM
    processing_timeout_seconds: int = 60
    estimated_processing_limit_seconds: int = 30
    cpu_threshold_percent: float = 85.0
    memory_threshold_percent: float = 90.0
    disk_threshold_percent: float = 95.0

    # Monitoring and alerting
    monitoring_enabled: bool = True
    log_retention_days: int = 90
    alert_response_time_seconds: int = 10
    anomaly_detection_time_seconds: int = 300  # 5 minutes

    # Security thresholds
    alert_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "error_rate_percent": 10.0,
            "response_time_seconds": 5.0,
            "memory_usage_percent": 80.0,
            "failed_auth_attempts": 5,
            "suspicious_ip_count": 10,
            "query_volume_increase_percent": 300.0,
            "entropy_threshold": 4.5,
        }
    )

    # Database configuration
    database_url: Optional[str] = None
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Environment-specific settings
    environment: str = "development"  # development, staging, production
    debug_mode: bool = False

    def set_alert_threshold(self, threshold_name: str, threshold_value: float) -> None:
        """
        Set an alert threshold value with validation.

        Args:
            threshold_name: Name of the threshold to set
            threshold_value: Value for the threshold (must be non-negative)

        Raises:
            ValueError: If threshold_value is negative
        """
        if threshold_value < 0:
            raise ValueError(
                f"Alert threshold '{threshold_name}' must be non-negative, got {threshold_value}"
            )

        self.alert_thresholds[threshold_name] = threshold_value

    def update_alert_thresholds(self, thresholds: Dict[str, float]) -> None:
        """
        Update multiple alert thresholds at once with validation.

        Args:
            thresholds: Dictionary of threshold names and values

        Raises:
            ValueError: If any threshold value is negative
        """
        for name, value in thresholds.items():
            if value < 0:
                raise ValueError(
                    f"Alert threshold '{name}' must be non-negative, got {value}"
                )

        self.alert_thresholds.update(thresholds)

    def validate(self) -> List[str]:
        """Validate configuration values and return list of errors."""
        errors = []

        # Validate numeric ranges
        if self.max_query_length <= 0:
            errors.append("max_query_length must be positive")

        if self.max_metadata_fields <= 0:
            errors.append("max_metadata_fields must be positive")

        if not 0.0 <= self.injection_detection_threshold <= 1.0:
            errors.append("injection_detection_threshold must be between 0.0 and 1.0")

        if not 0.0 <= self.injection_accuracy_target <= 1.0:
            errors.append("injection_accuracy_target must be between 0.0 and 1.0")

        if not 0.0 <= self.sanitization_confidence_threshold <= 1.0:
            errors.append(
                "sanitization_confidence_threshold must be between 0.0 and 1.0"
            )

        if self.rate_limit_per_minute <= 0:
            errors.append("rate_limit_per_minute must be positive")

        if self.rate_limit_burst <= 0:
            errors.append("rate_limit_burst must be positive")

        if self.processing_timeout_seconds <= 0:
            errors.append("processing_timeout_seconds must be positive")

        # Validate threshold percentages
        for threshold_name, threshold_value in [
            ("cpu_threshold_percent", self.cpu_threshold_percent),
            ("memory_threshold_percent", self.memory_threshold_percent),
            ("disk_threshold_percent", self.disk_threshold_percent),
        ]:
            if not 0.0 <= threshold_value <= 100.0:
                errors.append(f"{threshold_name} must be between 0.0 and 100.0")

        # Validate API key length constraints
        if self.api_key_min_length >= self.api_key_max_length:
            errors.append("api_key_min_length must be less than api_key_max_length")

        # Validate timeout values
        if self.auth_cache_validation_timeout_ms <= 0:
            errors.append("auth_cache_validation_timeout_ms must be positive")

        if self.auth_remote_fetch_timeout_ms <= 0:
            errors.append("auth_remote_fetch_timeout_ms must be positive")

        # Validate environment
        if self.environment not in ["development", "staging", "production"]:
            errors.append(
                "environment must be one of: development, staging, production"
            )

        return errors


@dataclass
class SecurityErrorResponse:
    """Standardized security error response structure."""

    error_code: str
    message: str  # Generic, non-revealing message
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert error response to dictionary."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
        }


# Additional model classes for completeness
@dataclass
class TokenBucket:
    """Represents a token bucket for rate limiting."""

    capacity: int
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: datetime = field(default_factory=datetime.now)
    time_provider: callable = field(default=datetime.now, compare=False, repr=False)

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self) -> None:
        """Refill the bucket based on elapsed time."""
        now = self.time_provider()
        elapsed = (now - self.last_refill).total_seconds()

        # Add tokens based on elapsed time and refill rate
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get the time to wait before tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds
        """
        self._refill()

        if self.tokens >= tokens:
            return 0.0

        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


@dataclass
class ResourceMetrics:
    """System resource utilization metrics."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    active_connections: int = 0
    response_time_ms: float = 0.0
    error_rate_percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def exceeds_thresholds(self, config: SecurityConfiguration) -> List[str]:
        """
        Check which thresholds are exceeded.

        Args:
            config: Security configuration with thresholds

        Returns:
            List of exceeded threshold names
        """
        exceeded = []

        if self.cpu_percent > config.cpu_threshold_percent:
            exceeded.append("cpu_threshold_percent")

        if self.memory_percent > config.memory_threshold_percent:
            exceeded.append("memory_threshold_percent")

        if self.disk_percent > config.disk_threshold_percent:
            exceeded.append("disk_threshold_percent")

        if self.error_rate_percent > config.alert_thresholds.get(
            "error_rate_percent", 10.0
        ):
            exceeded.append("error_rate_percent")

        if (
            self.response_time_ms
            > config.alert_thresholds.get("response_time_seconds", 5.0) * 1000
        ):
            exceeded.append("response_time_seconds")

        return exceeded
