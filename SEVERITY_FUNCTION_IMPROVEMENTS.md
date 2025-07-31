# Security Severity Function Improvements

## Issue Addressed

**Problem**: The `get_default_severity_for_event_type()` function assigned a single severity level per event type, but the docstring and enum descriptions suggested some events may have multiple severity levels depending on context.

**Location**: `src/security/models.py` lines 59-90

## Solution Implemented

### 1. Updated Documentation

**Enhanced `get_default_severity_for_event_type()` docstring**:
- Clarified that it returns **default/baseline** severity levels
- Added note about contextual variations documented in SecurityEventType enum
- Referenced new contextual function for context-specific severity
- Added examples showing default vs contextual scenarios
- Added inline comments explaining when events can have higher severity

### 2. Added Context-Based Severity Function

**New `get_contextual_severity_for_event_type()` function**:
- Accepts optional context dictionary with factors like frequency, impact, threat level
- Provides dynamic severity adjustment based on context
- Handles specific scenarios for events with multiple severity levels
- Comprehensive documentation with examples and parameter descriptions

### 3. Context-Aware Severity Logic

The new function handles contextual variations for these event types:

| Event Type | Default | Contextual Variations |
|------------|---------|----------------------|
| `RATE_LIMIT_EXCEEDED` | WARNING | ERROR (high frequency), INFO (low frequency) |
| `INPUT_VALIDATION_FAILURE` | ERROR | CRITICAL (high threat), WARNING (low threat) |
| `AUTHENTICATION_FAILURE` | ERROR | CRITICAL (multiple attempts, admin user) |
| `SUSPICIOUS_QUERY_PATTERN` | WARNING | ERROR (high confidence/threat) |
| `API_ACCESS_DENIED` | ERROR | WARNING (legitimate denial) |
| `CONFIGURATION_CHANGE` | INFO | WARNING (high impact, non-admin) |
| `SYSTEM_ERROR` | ERROR | CRITICAL (high impact, degraded system) |
| `RESOURCE_EXHAUSTION` | WARNING | ERROR (high impact, degraded system) |
| `UNAUTHORIZED_ACCESS_ATTEMPT` | ERROR | CRITICAL (admin user, critical threat) |

### 4. Context Parameters Supported

- `frequency`: Event frequency ('high', 'normal', 'low')
- `impact`: Impact level ('high', 'medium', 'low')
- `threat_level`: Threat assessment ('critical', 'high', 'medium', 'low')
- `system_state`: Current system state ('degraded', 'normal')
- `user_type`: User type ('admin', 'regular', 'anonymous')
- `attempt_count`: Number of attempts/occurrences
- `confidence_score`: Detection confidence (0.0 to 1.0)

## Usage Examples

### Basic Usage (Default Severity)
```python
severity = get_default_severity_for_event_type(SecurityEventType.RATE_LIMIT_EXCEEDED)
# Returns: SecuritySeverity.WARNING
```

### Advanced Usage (Contextual Severity)
```python
context = {'frequency': 'high', 'attempt_count': 100}
severity = get_contextual_severity_for_event_type(
    SecurityEventType.RATE_LIMIT_EXCEEDED, 
    context
)
# Returns: SecuritySeverity.ERROR (escalated from WARNING)
```

## Benefits Achieved

1. **Clarity**: Default function clearly documented as baseline/default
2. **Flexibility**: New contextual function handles complex scenarios
3. **Backward Compatibility**: Existing code continues to work unchanged
4. **Comprehensive**: Covers all event types mentioned in enum documentation
5. **Extensible**: Easy to add new context parameters and logic
6. **Well-Documented**: Extensive examples and parameter descriptions

## Files Created/Modified

- ✅ **Modified**: `src/security/models.py` - Updated functions and documentation
- ✅ **Created**: `src/security/SEVERITY_USAGE_GUIDE.md` - Comprehensive usage guide
- ✅ **Created**: `SEVERITY_FUNCTION_IMPROVEMENTS.md` - This summary document

## Testing

The implementation was tested with:
- Default severity function for all event types
- Contextual severity escalation scenarios
- Documentation examples verification
- Edge cases and parameter combinations

All tests passed, confirming the implementation works correctly and maintains backward compatibility while adding the requested contextual functionality.