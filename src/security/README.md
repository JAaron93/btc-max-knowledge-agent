# Security Middleware Integration

This document explains how to integrate the security validation middleware with FastAPI applications.

## Overview

The security middleware provides comprehensive input validation, request logging, and security event monitoring for FastAPI applications. It consists of two main components:

1. **SecurityValidationMiddleware**: Validates all incoming requests for malicious content
2. **SecurityHeadersMiddleware**: Adds security headers to all responses

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
config_manager = SecurityConfigurationManager()
security_config = config_manager.load_secure_config()

# Initialize security components
validator = SecurityValidator(security_config)
monitor = YourSecurityMonitor()  # Implement ISecurityMonitor

# Create and apply middleware
validation_middleware, headers_middleware = create_security_middleware(
    validator, monitor, security_config
)

app.add_middleware(validation_middleware)
app.add_middleware(headers_middleware)
```

### Integration with Existing Bitcoin Assistant API

To integrate with the existing `bitcoin_assistant_api.py`:

```python
# Add to the top of bitcoin_assistant_api.py
from src.security.integration_example import integrate_security_with_bitcoin_api

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

## Error Handling

### Validation Failures

When validation fails, the middleware returns appropriate HTTP status codes:

- `400 Bad Request`: Input validation failed
- `400 Bad Request`: Input sanitization required
- `500 Internal Server Error`: Internal security error

Example error response:

```json
{
  "error": "input_validation_failed",
  "message": "Request contains invalid or potentially malicious content",
  "request_id": "uuid",
  "violations": 2,
  "confidence_score": 0.95
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

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('src.security').setLevel(logging.DEBUG)
```

### Library Health

Check security library status:

```python
validator = SecurityValidator(config)
health_status = await validator.check_library_health()
print(health_status)
```

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