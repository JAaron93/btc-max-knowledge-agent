# Design Document

## Overview

This design implements a comprehensive security framework for the BTC Max Knowledge Agent's Pinecone Assistant API integration. The solution follows a defense-in-depth approach with multiple security layers, from input validation to monitoring and alerting. The design addresses common attack vectors against AI/ML systems including prompt injection, data exfiltration, authentication bypass, and resource exhaustion attacks.

## Architecture

### High-Level Architecture

```mermaid
graph TB
    Client[Client Request] --> InputSec[Input Security Layer]
    InputSec --> Auth[Authentication Layer]
    Auth --> QueryProc[Query Processing Security]
    QueryProc --> PineconeInt[Secure Pinecone Integration]
    PineconeInt --> Response[Secure Response Handler]
    
    Monitor[Security Monitor] --> InputSec
    Monitor --> Auth
    Monitor --> QueryProc
    Monitor --> PineconeInt
    
    Config[Security Configuration] --> InputSec
    Config --> Auth
    Config --> QueryProc
    Config --> PineconeInt
```

### Security Layers

1. **Input Security Layer**: Validates and sanitizes all incoming requests
2. **Authentication Layer**: Manages API authentication, rate limiting, and access control
3. **Query Processing Security**: Detects and prevents prompt injection and query manipulation
4. **Secure Pinecone Integration**: Provides secure wrapper around Pinecone API calls
5. **Security Monitoring**: Continuous monitoring, logging, and alerting for security events

## Components and Interfaces

### 1. SecurityValidator

**Purpose**: Input validation and sanitization service

**Interface**:
```python
class ISecurityValidator(ABC):
    @abstractmethod
    async def validate_input(self, input_data: str, context: Dict[str, Any]) -> ValidationResult:
        pass
    
    @abstractmethod
    async def sanitize_input(self, input_data: str) -> str:
        pass
```

**Key Features**:
- Input length validation (≤ 4 KB maximum)
- Format validation (UTF-8 encoding required)
- Malicious pattern detection using OWASP CRS v3.3.5 rules
- Content sanitization with HTML entity encoding
- Confidence scoring (≥ 0.8 for malicious patterns, ≥ 0.7 post-sanitization)
- Specific injection pattern detection (`<script>`, `'; DROP`, `$(`, `{{`, backticks, null bytes)

### 2. PromptInjectionDetector

**Purpose**: Detect and neutralize prompt injection attempts

**Interface**:
```python
class IPromptInjectionDetector(ABC):
    @abstractmethod
    async def detect_injection(self, query: str, context: Dict[str, Any]) -> DetectionResult:
        pass
    
    @abstractmethod
    async def neutralize_injection(self, query: str) -> str:
        pass
```

**Key Features**:
- Pattern-based injection detection with ≥95% accuracy
- Specific pattern recognition ("ignore previous instructions", "system:", "assistant:", role confusion, delimiter injection with `---`, `###`)
- Context-aware analysis for sophisticated attacks
- Query neutralization strategies for detected threats
- Context window protection (≤8192 tokens maximum)
- Parameter constraint enforcement (top_k: 1-50, similarity threshold: 0.1-1.0)

### 3. AuthenticationManager

**Purpose**: Handle API authentication and rate limiting

**Interface**:
```python
class IAuthenticationManager(ABC):
    @abstractmethod
    async def validate_credentials(self, credentials: Dict[str, str]) -> AuthResult:
        pass
    
    @abstractmethod
    async def check_rate_limit(self, client_id: str) -> RateLimitResult:
        pass
```

**Key Features**:
- API key validation (32-64 character alphanumeric) within 100ms
- JWT token validation (RS256/HS256 with exp claim)
- Rate limiting using token-bucket algorithm (bucket capacity: 10 tokens, refill rate: 1.67 tokens/second, sustained rate: 100 requests/minute)
- Progressive rate limiting with exponential backoff (1s, 2s, 4s, 8s)
- Temporary blocking (15 minutes after 5 violations)
- Suspicious pattern detection (>5 failed attempts in 60s, >10 IPs in 5 minutes)
- Client identification and tracking with risk scoring

**Token-Bucket Rate Limiting Design**:
- **Bucket Capacity**: 10 tokens (allows burst of up to 10 requests)
- **Refill Rate**: 1.67 tokens/second (100 tokens/minute ÷ 60 seconds)
- **Sustained Rate**: 100 requests/minute maximum
- **Burst Behavior**: Client can make 10 requests immediately, then limited to 1.67 requests/second
- **Mathematical Consistency**: Burst capacity (10) + sustained rate (1.67/sec) = 100 requests/minute maximum

### 4. SecurePineconeClient

**Purpose**: Secure wrapper around Pinecone API client

**Interface**:
```python
class ISecurePineconeClient(ABC):
    @abstractmethod
    async def secure_query(self, query: SecureQuery) -> SecureResponse:
        pass
    
    @abstractmethod
    async def validate_response(self, response: Any) -> ValidationResult:
        pass
```

**Key Features**:
- Secure connection management with encrypted protocols
- Query parameter validation (≤4 KB input, ≤1000 tokens, ≤50 metadata fields)
- Processing limits (60-second timeout, 30-second estimated processing time limit)
- Response filtering and validation for data exfiltration prevention
- Connection pooling with security controls (≤50 concurrent per IP, ≤200 system-wide)
- Resource monitoring (CPU ≤85%, memory ≤90%, disk ≤95%)

### 5. SecurityMonitor

**Purpose**: Security monitoring, logging, and alerting

**Interface**:
```python
class ISecurityMonitor(ABC):
    @abstractmethod
    async def log_security_event(self, event: SecurityEvent) -> None:
        pass
    
    @abstractmethod
    async def detect_anomalies(self, metrics: Dict[str, Any]) -> List[Anomaly]:
        pass
```

**Key Features**:
- Structured JSON security event logging with ISO 8601 timestamps
- 90-day minimum log retention policy with PostgreSQL backend
- Real-time alert generation (within 10 seconds for attacks, 5 minutes for anomalies)
- Anomaly detection (>300% query volume increase, entropy >4.5, geographic anomalies)
- Automatic protective measures when thresholds breached (error rate >10%, response time >5s, memory >80%)
- Security metrics collection and dashboard integration

### Security Logging Architecture

**Database Schema Design**:
```sql
-- Security events table with partitioning for performance
CREATE TABLE security_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id VARCHAR(255) NOT NULL UNIQUE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    source_ip INET,
    user_agent TEXT,
    client_id VARCHAR(255),
    details JSONB NOT NULL,
    mitigation_action VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

CREATE INDEX idx_security_events_timestamp   ON security_events (timestamp);
CREATE INDEX idx_security_events_type        ON security_events (event_type);
CREATE INDEX idx_security_events_severity    ON security_events (severity);
CREATE INDEX idx_security_events_source_ip   ON security_events (source_ip);
CREATE INDEX idx_security_events_client_id   ON security_events (client_id);
-- Create monthly partitions for efficient data management
CREATE TABLE security_events_y2024m01 PARTITION OF security_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Security metrics aggregation table
CREATE TABLE security_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,2) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tags JSONB,
    
    INDEX idx_security_metrics_name_time (metric_name, timestamp),
    INDEX idx_security_metrics_tags (tags)
);

-- Alert history table
CREATE TABLE security_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    related_events UUID[] DEFAULT '{}',
    
    INDEX idx_security_alerts_type (alert_type),
    INDEX idx_security_alerts_status (status),
    INDEX idx_security_alerts_triggered (triggered_at)
);
```

**Logging Implementation**:
```python
import json
from datetime import datetime, timedelta
from typing import Optional

class PostgreSQLSecurityLogger:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    async def init(self) -> None:
        self.pool = await asyncpg.create_pool(self._dsn)
        
    async def log_security_event(self, event: SecurityEvent) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO security_events 
                (event_id, timestamp, event_type, severity, source_ip, 
                 user_agent, client_id, details, mitigation_action)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, 
            event.event_id, event.timestamp, event.event_type.value,
            event.severity.value, event.source_ip, event.user_agent,
            event.client_id, json.dumps(event.details), event.mitigation_action)
    
    async def cleanup_old_logs(self) -> None:
        """Remove logs older than 90 days"""
        cutoff_date = datetime.now() - timedelta(days=90)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM security_events WHERE timestamp < $1", 
                cutoff_date
            )

**Required Dependencies**:
```python
# requirements.txt additions for logging
asyncpg>=0.28.0          # PostgreSQL async driver
psycopg2-binary>=2.9.0   # PostgreSQL sync driver (backup)
alembic>=1.12.0          # Database migrations
sqlalchemy>=2.0.0        # ORM for complex queries
```

**Environment Configuration**:
```python
# .env additions
DATABASE_URL=postgresql://user:password@localhost:5432/btc_security_logs
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
LOG_RETENTION_DAYS=90
ENABLE_LOG_PARTITIONING=true

# For production with Neon
NEON_DATABASE_URL=postgresql://user:password@ep-xxx.us-east-1.aws.neon.tech/btc_security_logs
```

**Migration Strategy**:
1. **Development**: Local PostgreSQL with Docker
2. **Staging**: Managed PostgreSQL (AWS RDS/Google Cloud SQL)
3. **Production**: Neon PostgreSQL for serverless scaling

**Performance Optimizations**:
- Monthly table partitioning for efficient queries and cleanup
- Proper indexing on frequently queried columns
- Connection pooling to handle concurrent logging
- Batch insertion for high-volume events
- Automated cleanup job for 90-day retention

### 6. ConfigurationValidator

**Purpose**: Validate and manage security configurations

**Interface**:
```python
class IConfigurationValidator(ABC):
    @abstractmethod
    async def validate_config(self, config: SecurityConfig) -> ValidationResult:
        pass
    
    @abstractmethod
    async def load_secure_config(self) -> SecurityConfig:
        pass
```

**Key Features**:
- Configuration validation on startup
- Secure environment variable handling
- Configuration change detection
- Fail-safe configuration loading

## Data Models

### Security Enums

```python
from enum import Enum

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

@dataclass
class SecurityViolation:
    """Represents a specific security violation detected during validation."""
    violation_type: str
    severity: SecuritySeverity
    description: str
    detected_pattern: Optional[str]
    confidence_score: float
    location: Optional[str]  # Where in the input the violation was found
    suggested_fix: Optional[str]
```

### SecurityEvent
```python
@dataclass
class SecurityEvent:
    event_id: str
    timestamp: datetime
    event_type: SecurityEventType
    severity: SecuritySeverity
    source_ip: Optional[str]
    user_agent: Optional[str]
    details: Dict[str, Any]
    mitigation_action: Optional[str]
```

### ValidationResult
```python
@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    violations: List[SecurityViolation]
    sanitized_input: Optional[str]
    recommended_action: SecurityAction
```

### DetectionResult
```python
@dataclass
class DetectionResult:
    injection_detected: bool
    confidence_score: float
    detected_patterns: List[str]
    injection_type: Optional[str]  # e.g., "role_confusion", "delimiter_injection", "instruction_override"
    risk_level: SecuritySeverity
    neutralized_query: Optional[str]
    recommended_action: SecurityAction
```

### AuthenticationContext
```python
@dataclass
class AuthenticationContext:
    client_id: str
    api_key_hash: str
    permissions: List[str]
    rate_limit_remaining: int
    last_request_time: datetime
    risk_score: float
```

### SecurityConfiguration
```python
from dataclasses import dataclass, field

@dataclass
class SecurityConfiguration:
    # Input validation limits
    max_query_length: int = 4096  # 4 KB maximum
    max_metadata_fields: int = 50
    max_context_tokens: int = 8192
    
    # Authentication and rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 10  # requests per second
    auth_validation_timeout_ms: int = 100
    api_key_min_length: int = 32
    api_key_max_length: int = 64
    
    # Prompt injection detection
    injection_detection_threshold: float = 0.8
    injection_accuracy_target: float = 0.95
    sanitization_confidence_threshold: float = 0.7
    
    # Resource limits
    max_concurrent_per_ip: int = 50
    max_concurrent_system: int = 200
    processing_timeout_seconds: int = 60
    cpu_threshold_percent: float = 85.0
    memory_threshold_percent: float = 90.0
    disk_threshold_percent: float = 95.0
    
    # Monitoring and alerting
    monitoring_enabled: bool = True
    log_retention_days: int = 90
    alert_response_time_seconds: int = 10
    anomaly_detection_time_seconds: int = 300
    
    # Security thresholds
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "error_rate_percent": 10.0,
        "response_time_seconds": 5.0,
        "memory_usage_percent": 80.0,
        "failed_auth_attempts": 5,
        "suspicious_ip_count": 10
    })
```

## Error Handling

### Security-First Error Handling Strategy

1. **Fail Securely**: All security failures default to denying access
2. **Consistent Responses**: Standardized error responses prevent information leakage
3. **Secure Logging**: Log security events without exposing sensitive data
4. **Graceful Degradation**: Maintain service availability under attack

### Error Response Structure
```python
@dataclass
class SecurityErrorResponse:
    error_code: str
    message: str  # Generic, non-revealing message
    timestamp: datetime
    request_id: str
    # Internal details logged separately, not exposed to client
```

### Error Categories
- **INPUT_VALIDATION_FAILED**: Invalid or malicious input detected
- **AUTHENTICATION_FAILED**: Invalid credentials or expired tokens
- **RATE_LIMIT_EXCEEDED**: Client exceeded allowed request rate
- **INJECTION_DETECTED**: Prompt injection attempt identified
- **RESOURCE_EXHAUSTION**: System resources under pressure
- **CONFIGURATION_ERROR**: Security configuration issues

## Testing Strategy

### Security Testing Approach

1. **Unit Testing**:
   - Test each security component in isolation
   - Mock external dependencies
   - Validate security logic and edge cases

2. **Integration Testing**:
   - Test security layer interactions
   - Validate end-to-end security flows
   - Test with realistic attack scenarios

3. **Security Testing**:
   - Penetration testing simulation
   - Fuzzing input validation
   - Load testing under attack conditions
   - Compliance validation

4. **Performance Testing**:
   - Security overhead measurement
   - Scalability under security constraints
   - Resource usage optimization

### Test Categories

**Input Validation Tests**:
- Malicious input patterns
- Boundary condition testing
- Encoding and escaping validation

**Authentication Tests**:
- Invalid credential handling
- Token expiration scenarios
- Rate limiting effectiveness

**Injection Detection Tests**:
- Known prompt injection patterns
- Context manipulation attempts
- Evasion technique testing

**Monitoring Tests**:
- Alert generation accuracy
- Log integrity and completeness
- Anomaly detection effectiveness

### Continuous Security Testing

- Automated security test suite in CI/CD
- Regular security scanning and updates
- Threat model validation
- Security metrics monitoring

## Integration Points

### Existing System Integration

1. **Logging Infrastructure**: Integrate with existing optimized logging system
2. **Configuration Management**: Use existing environment variable patterns
3. **Error Handling**: Extend current error handling framework
4. **Monitoring**: Integrate with existing monitoring and alerting systems

### API Integration Points

- **FastAPI Middleware**: Security validation middleware
- **Pinecone Client**: Secure wrapper around existing client
- **Gradio Interface**: Security controls for UI interactions
- **TTS Service**: Secure integration with text-to-speech functionality
- **PostgreSQL Database**: Security event logging and metrics storage
- **Neon PostgreSQL**: Production-ready serverless PostgreSQL for scaling

### Development Setup

**Local Development with Docker**:
```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: btc_security_logs
      POSTGRES_USER: btc_user
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
    command: postgres -c log_statement=all -c log_destination=stderr

volumes:
  postgres_data:
```

**Database Migration Management**:
```python
# alembic/env.py configuration
from alembic import context
from sqlalchemy import engine_from_config, pool
from src.security.models import Base

config = context.config
target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True
        )
        
        with context.begin_transaction():
            context.run_migrations()
```

## Security Best Practices

1. **Principle of Least Privilege**: Minimal required permissions
2. **Defense in Depth**: Multiple security layers
3. **Zero Trust**: Validate all inputs and interactions
4. **Secure by Default**: Safe default configurations
5. **Continuous Monitoring**: Real-time security awareness
6. **Regular Updates**: Keep security measures current