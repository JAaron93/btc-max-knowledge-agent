"""
Data models and enums for security components.

This module defines all data structures used throughout the security system,
including events, results, configurations, and supporting enums.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Union, TypedDict
import uuid


class SecurityEventType(Enum):
    """Enumeration of security event types for classification and filtering."""
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHENTICATION_SUCCESS = "authentication_success"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INPUT_VALIDATION_FAILURE = "input_validation_failure"
    PROMPT_INJECTION_DETECTED = "prompt_injection_detected"
    SUSPICIOUS_QUERY_PATTERN = "suspicious_query_pattern"
    API_ACCESS_DENIED = "api_access_denied"
    CONFIGURATION_CHANGE = "configuration_change"
    SYSTEM_ERROR = "system_error"
    DATA_EXFILTRATION_ATTEMPT = "data_exfiltration_attempt"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNAUTHORIZED_ACCESS_ATTEMPT = "unauthorized_access_attempt"


class SecuritySeverity(Enum):
    """Enumeration of security event severity levels for prioritization and alerting."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


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
    """Represents a specific security violation detected during validation."""
    violation_type: str
    severity: SecuritySeverity
    description: str
    detected_pattern: Optional[str] = None
    confidence_score: float = 0.0
    location: Optional[str] = None  # Where in the input the violation was found
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
    injection_type: Optional[str] = None  # e.g., "role_confusion", "delimiter_injection"
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
            "mitigation_action": self.mitigation_action
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


@dataclass
class Anomaly:
    """Represents a detected security anomaly."""
    anomaly_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    anomaly_type: str = "unknown"
    severity: SecuritySeverity = SecuritySeverity.WARNING
    description: str = ""
    metrics: AnomalyMetrics = field(default_factory=dict)
    threshold_exceeded: Optional[str] = None
    recommended_actions: List[str] = field(default_factory=list)


@dataclass
class SecureQuery:
    """Represents a validated and secure query for Pinecone."""
    
    # Class-level constants for validation limits
    MAX_TOP_K = 50  # Maximum number of results to return (MAX_METADATA_FIELDS limit)
    MAX_QUERY_SIZE = 4096  # Maximum query text size in bytes (4KB, MAX_REQUEST_SIZE limit)
    
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
        
        if len(self.query_text.encode('utf-8')) > self.MAX_QUERY_SIZE:
            raise ValueError(f"Query text exceeds maximum size of {self.MAX_QUERY_SIZE // 1024}KB")


@dataclass
class SecureResponse:
    """Represents a validated and filtered response from Pinecone."""
    matches: List[Dict[str, Any]] = field(default_factory=list)
    namespace: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    filtered_content: List[str] = field(default_factory=list)  # Content removed for security
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
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "error_rate_percent": 10.0,
        "response_time_seconds": 5.0,
        "memory_usage_percent": 80.0,
        "failed_auth_attempts": 5,
        "suspicious_ip_count": 10,
        "query_volume_increase_percent": 300.0,
        "entropy_threshold": 4.5
    })
    
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
            raise ValueError(f"Alert threshold '{threshold_name}' must be non-negative, got {threshold_value}")
        
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
                raise ValueError(f"Alert threshold '{name}' must be non-negative, got {value}")
        
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
            errors.append("sanitization_confidence_threshold must be between 0.0 and 1.0")
        
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
            ("disk_threshold_percent", self.disk_threshold_percent)
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
            errors.append("environment must be one of: development, staging, production")
        
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
            "request_id": self.request_id
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
        
        if self.error_rate_percent > config.alert_thresholds.get("error_rate_percent", 10.0):
            exceeded.append("error_rate_percent")
        
        if self.response_time_ms > config.alert_thresholds.get("response_time_seconds", 5.0) * 1000:
            exceeded.append("response_time_seconds")
        
        return exceeded