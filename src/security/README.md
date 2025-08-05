# Security Middleware Integration

This document explains how to integrate the security validation middleware with FastAPI applications.

## Overview

The security middleware provides comprehensive input validation, request logging, and security event monitoring for FastAPI applications. It consists of two main components:

1. **SecurityValidationMiddleware**: Validates all incoming requests for malicious content
2. **SecurityHeadersMiddleware**: Adds security headers to all responses

## Key Components

The security system consists of several key classes that work together:

- **SecurityValidator** (`src/security/validator.py`): Performs comprehensive input validation and sanitization using multiple security libraries (libinjection, bleach, etc.)
- **SecurityConfigurationManager** (`src/security/config.py`): Handles loading and validating security configuration from environment variables with proper type conversion and validation
- **ISecurityMonitor** (`src/security/interfaces.py`): Interface for security monitoring implementations that log events, detect anomalies, and generate alerts
- **SecurityValidationMiddleware** (`src/security/middleware.py`): FastAPI middleware that intercepts requests and applies security validation
- **SecurityHeadersMiddleware** (`src/security/middleware.py`): FastAPI middleware that adds standard security headers to responses

> **Note**: For a complete working example with a mock security monitor, see `src/security/demo_integration.py`

## Quick Start

### Basic Integration

```python
from fastapi import FastAPI
from src.security.middleware import create_security_middleware
from src.security.validator import SecurityValidator
from src.security.config import SecurityConfigurationManager

# Create FastAPI app
app = FastAPI()

# Load security configuration
# SecurityConfigurationManager: Handles loading and validating security settings from environment variables
config_manager = SecurityConfigurationManager()
security_config = config_manager.load_secure_config()

# Initialize security components
# SecurityValidator: Performs input validation and sanitization using multiple security libraries
validator = SecurityValidator(security_config)
# YourSecurityMonitor: Implement ISecurityMonitor interface for logging events and detecting anomalies
# For demo purposes, you can use MockSecurityMonitor from demo_integration.py
monitor = YourSecurityMonitor()  # Implement ISecurityMonitor

# Create middleware factory functions (returns classes, not instances)
validation_middleware, headers_middleware = create_security_middleware(
    validator, monitor, security_config
)

# Add middleware classes to FastAPI (FastAPI will instantiate them)
app.add_middleware(validation_middleware)
app.add_middleware(headers_middleware)
```

**Important Note:** The `create_security_middleware` function returns middleware classes (factory functions), not instances. This is exactly what FastAPI's `add_middleware()` method expects. FastAPI will automatically instantiate the middleware classes when processing requests.

#### ✅ Correct Usage:

#### ❌ Incorrect Usage:
```python
# This will cause TypeError - don't instantiate manually
validation_middleware, headers_middleware = create_security_middleware(validator, monitor, config)
app.add_middleware(validation_middleware())  # Don't call it!
app.add_middleware(headers_middleware())     # Don't call it!

# This will also cause TypeError - don't wrap in Middleware class
from fastapi import Middleware
app.add_middleware(Middleware(validation_middleware))  # Don't wrap it!
```

### Integration with Existing Bitcoin Assistant API

To integrate with the existing `bitcoin_assistant_api.py`:

```python
# Add to the top of bitcoin_assistant_api.py
from src.security.integration_example import integrate_security_with_bitcoin_api
from logging import getLogger
logger = getLogger(__name__)

# After creating the FastAPI app
app = FastAPI(...)

# Integrate security middleware
try:
    security_integration = integrate_security_with_bitcoin_api(app)
    logger.info("Security middleware integrated successfully")
except Exception as e:
    logger.error(f"Failed to integrate security: {e}")
    # Handle error appropriately
```

## Configuration

### Environment Variables

The middleware uses the following environment variables:

```bash
# Input validation limits
MAX_QUERY_LENGTH=4096
MAX_METADATA_FIELDS=50
MAX_CONTEXT_TOKENS=8192

# Rate limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=10

# Authentication timeouts
AUTH_CACHE_VALIDATION_TIMEOUT_MS=100
AUTH_REMOTE_FETCH_TIMEOUT_MS=300

# Security thresholds
INJECTION_DETECTION_THRESHOLD=0.8
SANITIZATION_CONFIDENCE_THRESHOLD=0.7

# Monitoring
MONITORING_ENABLED=true
LOG_RETENTION_DAYS=90

# Environment
ENVIRONMENT=production
DEBUG_MODE=false
```

### Exempt Paths

By default, the following paths are exempt from validation:

- `/health`
- `/docs`
- `/openapi.json`
- `/redoc`
- `/favicon.ico`

You can customize exempt paths:

```python
validation_middleware, headers_middleware = create_security_middleware(
    validator, monitor, security_config,
    exempt_paths=["/health", "/custom-exempt-path"]
)
```

## Features

### Input Validation

The middleware validates:

- Request body content for malicious patterns
- Query parameters for injection attempts
- Input length limits
- UTF-8 encoding validity

#### Advanced Prompt Injection Detection

The system includes sophisticated prompt injection detection with technical-aware analysis:

- **Technical Term Recognition**: Identifies common Bitcoin, blockchain, and programming terms
- **Adaptive Repetition Thresholds**: Uses higher thresholds (40% vs 30%) for technical queries to reduce false positives
- **Context-Aware Analysis**: Considers technical term density when evaluating word repetition patterns
- **Selective Filtering**: Focuses on non-technical word repetition for more accurate injection detection

**Note**: The repetition thresholds (40% and 30%) are evaluated independently and prior to the global `INJECTION_DETECTION_THRESHOLD=0.8` defined in the Security thresholds section. The repetition analysis determines if content has suspicious patterns, while the global threshold controls the overall confidence score for blocking requests. To reduce false positives, adjust the repetition thresholds; to change overall detection sensitivity, modify the global threshold.

See the "Security thresholds" table (around line 117) for the exact environment variable names including `INJECTION_DETECTION_THRESHOLD` and other configurable security parameters.

This prevents legitimate technical queries like "Bitcoin mining uses Bitcoin blockchain technology for Bitcoin transaction validation" from being incorrectly flagged as injection attempts.

### Security Headers

Automatically adds security headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: ...`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: ...`

### Security Event Logging

All security events are logged with structured data:

```json
{
  "event_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "event_type": "input_validation_failure",
  "severity": "critical",
  "source_ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "details": {
    "path": "/query",
    "method": "POST",
    "violations": [...]
  }
}
```

#### Event Types and Severity Levels

The middleware logs various types of security events with appropriate severity levels:

**Informational Events (INFO):**
- `input_validation_success`: Successful input validation (for monitoring)
- `authentication_success`: Successful authentication
- `configuration_change`: Security configuration changes
- `request_success`: Normal request completion

**Warning Events (WARNING):**
- `rate_limit_exceeded`: Rate limiting triggered
- `suspicious_query_pattern`: Unusual query patterns detected
- `resource_exhaustion`: System resource limits approached

**Error Events (ERROR):**
- `input_validation_failure`: Malicious input detected
- `authentication_failure`: Failed authentication attempts
- `api_access_denied`: Unauthorized API access
- `system_error`: Internal security system errors
- `unauthorized_access_attempt`: Access control violations

**Critical Events (CRITICAL):**
- `prompt_injection_detected`: AI prompt injection attempts
- `data_exfiltration_attempt`: Potential data theft attempts

Events marked as INFO (like `input_validation_success`) are logged for monitoring and metrics but do not trigger alerts. Error and Critical events automatically trigger security alerts.

## Error Handling

### Validation Failures

When validation fails, the middleware returns appropriate HTTP status codes:

- `400 Bad Request`: Input validation failed (malicious content detected)
- `422 Unprocessable Entity`: Input sanitization required (content needs cleaning)
- `500 Internal Server Error`: Internal security error

Example error responses:

**400 Bad Request (Input validation failed):**
```json
{
  "error": "input_validation_failed",
  "message": "Request contains invalid or potentially malicious content",
  "request_id": "uuid",
  "violations": 2,
  "confidence_score": 0.95
}
```

**422 Unprocessable Entity (Input sanitization required):**
```json
{
  "error": "input_sanitization_required",
  "message": "Request content requires sanitization",
  "request_id": "uuid",
  "violations": 1,
  "confidence_score": 0.8
}
```

### Graceful Degradation

The middleware is designed to fail securely:

- If validation fails, requests are blocked
- If logging fails, requests continue but errors are logged
- If configuration is invalid, the application fails to start

## Testing

### Unit Tests

Run the middleware tests:

```bash
python -m pytest tests/test_security_middleware_simple.py -v
```

### Integration Testing

Test with malicious payloads:

```python
from fastapi.testclient import TestClient

client = TestClient(app)

# Test XSS injection
response = client.post("/query", json={
    "query": "<script>alert('xss')</script>"
})
assert response.status_code == 400

# Test SQL injection
response = client.post("/query", json={
    "query": "'; DROP TABLE users; --"
})
assert response.status_code == 400
```

## Monitoring

### Security Status Endpoints

The integration adds monitoring endpoints:

- `GET /security/status`: Current security system status
- `GET /security/health`: Security system health check

### Metrics

Monitor these key metrics:

- Validation success/failure rates
- Response times
- Security event counts by type
- Library health status

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all security modules are properly installed
2. **Configuration Errors**: Check environment variables are set correctly
3. **Performance Issues**: Monitor validation response times
4. **False Positives**: Adjust confidence thresholds if needed
5. **Middleware TypeError**: If you get "TypeError: 'SecurityValidationMiddleware' object is not callable", you're trying to pass middleware instances instead of classes to `add_middleware()`. Use `create_security_middleware()` which returns classes, not instances.
6. **Middleware Not Applied**: Ensure middleware is added in the correct order - validation middleware should be added before headers middleware

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('src.security').setLevel(logging.DEBUG)
```

### Library Health

Check security library status:

**In an async context (e.g., FastAPI endpoint):**
```python
async def check_security_health():
    from src.security.validator import SecurityValidator
    from src.security.config import SecurityConfigurationManager

    config = SecurityConfigurationManager().load_secure_config()
    validator = SecurityValidator(config)
    health_status = await validator.check_library_health()
    print(health_status)

# Usage in FastAPI endpoint:
# @app.get("/security/health")
# async def get_security_health():
#     return await check_security_health()
```

**In a synchronous script:**
```python
import asyncio
from src.security.validator import SecurityValidator
from src.security.config import SecurityConfigurationManager

config = SecurityConfigurationManager().load_secure_config()
validator = SecurityValidator(config)
health_status = asyncio.run(validator.check_library_health())
print(health_status)
```

**In synchronous code with anyio (recommended for libraries):**
```python
import anyio
from security.middleware import SecurityValidator
from security.models import SecurityConfig

config = SecurityConfig()
validator = SecurityValidator(config)
health_status = anyio.from_thread.run(validator.check_library_health)
print(health_status)
```

**Note**: Use `await` when already in an async context (FastAPI endpoints, async functions). Use `asyncio.run()` only in standalone scripts or the main entry point. Use `anyio.from_thread.run()` when calling from synchronous code that might be running inside an existing event loop.

## Security Considerations

1. **Fail Secure**: Always block requests when in doubt
2. **Log Everything**: Comprehensive security event logging
3. **Regular Updates**: Keep security libraries updated
4. **Monitor Actively**: Set up alerts for security events
5. **Test Regularly**: Run security tests in CI/CD pipeline

## Performance Impact

The middleware adds minimal overhead:

- Validation: ~1-5ms per request
- Logging: ~0.5-1ms per request
- Headers: ~0.1ms per request

Monitor performance in production and adjust configuration as needed.

## Quick Reference

### Key Classes and Their Locations

| Class | File | Purpose |
|-------|------|---------|
| `SecurityValidator` | `src/security/validator.py` | Input validation and sanitization |
| `SecurityConfigurationManager` | `src/security/config.py` | Configuration loading and validation |
| `ISecurityMonitor` | `src/security/interfaces.py` | Security monitoring interface |
| `SecurityValidationMiddleware` | `src/security/middleware.py` | Request validation middleware |
| `SecurityHeadersMiddleware` | `src/security/middleware.py` | Security headers middleware |
| `MockSecurityMonitor` | `src/security/demo_integration.py` | Demo monitoring implementation |

### Essential Functions

- `create_security_middleware()`: Factory function to create middleware classes
- `integrate_security_with_bitcoin_api()`: Helper for Bitcoin API integration
- `setup_src_path()`: Test utility for robust imports (in `tests/test_utils.py`)

### Quick Integration

```python
from src.security.demo_integration import create_secure_bitcoin_api

# Create secure FastAPI app with all security components
app = create_secure_bitcoin_api()
```