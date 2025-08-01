# Security Event Severity Usage Guide

## Overview

The security system provides two functions for determining event severity:

1. **`get_default_severity_for_event_type()`** - Returns baseline/default severity
2. **`get_contextual_severity_for_event_type()`** - Returns context-aware severity

## When to Use Each Function

### Use Default Severity When:
- You need a consistent baseline severity for logging
- Context information is not available
- Setting up initial alerting thresholds
- Creating simple event classifications

### Use Contextual Severity When:
- You have additional context about the event
- You need dynamic severity based on threat level
- Implementing adaptive security responses
- Fine-tuning alerting to reduce false positives

## Examples

### Basic Usage (Default Severity)

```python
from security.models import (
    SecurityEventType,
    SecuritySeverity,                # ← add
    get_contextual_severity_for_event_type,
)

# Get baseline severity for rate limiting
severity = get_default_severity_for_event_type(SecurityEventType.RATE_LIMIT_EXCEEDED)
# Returns: SecuritySeverity.WARNING

# Log with default severity
logger.log(severity.value, f"Rate limit exceeded for user {user_id}")
```

### Advanced Usage (Contextual Severity)

```python
from security.models import (
    SecurityEventType,
    SecuritySeverity,          # ← add
    get_default_severity_for_event_type,
)

# High-frequency rate limiting becomes more severe
context = {
    'frequency': 'high',
    'attempt_count': 150,
    'user_type': 'anonymous'
}

severity = get_contextual_severity_for_event_type(
    SecurityEventType.RATE_LIMIT_EXCEEDED, 
    context
)
# Returns: SecuritySeverity.ERROR (escalated from WARNING)

# Input validation with threat assessment
context = {
    'threat_level': 'critical',
    'confidence_score': 0.95,
    'pattern': 'sql_injection'
}

severity = get_contextual_severity_for_event_type(
    SecurityEventType.INPUT_VALIDATION_FAILURE,
    context
)
# Returns: SecuritySeverity.CRITICAL (escalated from ERROR)
```

### Real-World Integration

```python
def handle_security_event(event_type, details=None):
    """Handle a security event with appropriate severity."""
    
    # Start with default severity
    default_severity = get_default_severity_for_event_type(event_type)
    
    # Use contextual severity if we have additional information
    if details:
        actual_severity = get_contextual_severity_for_event_type(event_type, details)
    else:
        actual_severity = default_severity
    
    # Log the event
    logger.log(actual_severity.value, f"Security event: {event_type.value}")
    
    # Take action based on severity
    if actual_severity == SecuritySeverity.CRITICAL:
        trigger_immediate_alert(event_type, details)
        block_suspicious_activity()
    elif actual_severity == SecuritySeverity.ERROR:
        schedule_investigation(event_type, details)
    elif actual_severity == SecuritySeverity.WARNING:
        update_monitoring_metrics(event_type)
```

## Context Parameters

The contextual severity function accepts these context parameters:

| Parameter | Type | Description | Example Values |
|-----------|------|-------------|----------------|
| `frequency` | str | Event frequency | 'high', 'normal', 'low' |
| `impact` | str | Impact level | 'high', 'medium', 'low' |
| `threat_level` | str | Threat assessment | 'critical', 'high', 'medium', 'low' |
| `system_state` | str | Current system state | 'degraded', 'normal' |
| `user_type` | str | User type | 'admin', 'regular', 'anonymous' |
| `attempt_count` | int | Number of attempts | 1, 5, 100, etc. |
| `confidence_score` | float | Detection confidence | 0.0 to 1.0 |
| `pattern` | str | Attack/threat pattern type | 'sql_injection', 'xss', 'command_injection', 'brute_force' |

## Event Types with Contextual Variations

These event types have different severities based on context:

### RATE_LIMIT_EXCEEDED
- **Default**: WARNING
- **High frequency/count**: ERROR
- **Low frequency/count**: INFO

### INPUT_VALIDATION_FAILURE
- **Default**: ERROR
- **High threat/confidence**: CRITICAL
- **Low threat/confidence**: WARNING

### AUTHENTICATION_FAILURE
- **Default**: ERROR
- **Multiple attempts/admin user**: CRITICAL

### SUSPICIOUS_QUERY_PATTERN
- **Default**: WARNING
- **High confidence/threat**: ERROR

### API_ACCESS_DENIED
- **Default**: ERROR
- **Legitimate denial**: WARNING

### CONFIGURATION_CHANGE
- **Default**: INFO
- **High impact/non-admin**: WARNING

### SYSTEM_ERROR
- **Default**: ERROR
- **High impact/degraded system**: CRITICAL

### RESOURCE_EXHAUSTION
- **Default**: WARNING
- **High impact/degraded system**: ERROR

### UNAUTHORIZED_ACCESS_ATTEMPT
- **Default**: ERROR
- **Admin user/critical threat**: CRITICAL

## Best Practices

1. **Always start with default severity** for consistent baseline behavior
2. **Use contextual severity** when you have meaningful context data
3. **Document your context parameters** when calling the contextual function
4. **Test both functions** in your security event handling code
5. **Monitor severity distributions** to tune your context parameters
6. **Consider caching** contextual severity results for high-frequency events