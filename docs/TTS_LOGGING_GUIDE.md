# TTS Logging Configuration Guide

## Overview

The TTS feature includes comprehensive logging for operations tracking, error monitoring, and performance analysis. This guide explains how to configure and use the logging system effectively.

## Log Levels

The TTS system uses standard Python logging levels:

- **DEBUG**: Detailed information for debugging (cache operations, API calls)
- **INFO**: General operational information (synthesis requests, recovery)
- **WARNING**: Important events that don't stop operation (API key issues, retries)
- **ERROR**: Error conditions that may affect functionality
- **CRITICAL**: Serious errors that may cause system failure

## Configuration

### Environment Variables

Set the logging level using environment variables:

```bash
# Global log level
export LOG_LEVEL=INFO

# Component-specific logging
export TTS_LOG_LEVEL=DEBUG
export CACHE_LOG_LEVEL=INFO
export ERROR_HANDLER_LOG_LEVEL=WARNING
```

**Note**: The application startup code is responsible for reading each environment variable (e.g., using `os.getenv('TTS_LOG_LEVEL')`) and explicitly setting the log level on the corresponding logger via `logging.getLogger(...).setLevel()`. The Python logging library does not automatically detect these environment variables.

### Programmatic Configuration

For development and testing, configure logging programmatically:

```python
import logging
import sys

# Create a formatter for consistent log output
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create a console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

# Configure TTS component loggers
tts_loggers = [
    'utils.tts_service',
    'utils.tts_error_handler', 
    'utils.multi_tier_audio_cache',
    'utils.audio_utils'
]

for logger_name in tts_loggers:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    logger.propagate = False  # Prevent duplicate logs from root logger

# Example usage - these will now output logs
tts_logger = logging.getLogger('utils.tts_service')
tts_logger.info("TTS service initialized")
tts_logger.debug("Debug information will be visible")
```

## Log Categories

### TTS Service Operations

**Logger**: `utils.tts_service`

**Key Events**:
- Service initialization and configuration
- Synthesis request processing
- Cache hit/miss events
- Performance metrics
- Memory cleanup operations

**Example Logs**:
```
INFO - TTS service initialized with connection pooling and memory management
INFO - TTS synthesis request: 245 characters, voice: JBFqnCBsd6RMkjVDRZzb
INFO - TTS cache hit: returning 15234 bytes of cached audio
INFO - Successfully synthesized 15234 bytes of audio in 1.23s (cached as a1b2c3d4...)
DEBUG - Memory cleanup performed: {'cache_entries_removed': 5, 'temp_files_cleaned': 2}
```

### Content Processing

**Logger**: `utils.audio_utils`

**Key Events**:
- Content extraction from responses
- Text cleaning operations
- Format validation
- Processing errors

**Example Logs**:
```
INFO - Starting content extraction from 1024 characters
DEBUG - After markdown cleaning: 987 characters
DEBUG - After source removal: 856 characters
DEBUG - After metadata removal: 834 characters
INFO - Content extraction successful: 834 characters extracted from 1024 original characters
```

### Error Handling

**Logger**: `utils.tts_error_handler`

**Key Events**:
- Circuit breaker state changes
- Retry attempts and backoff
- Recovery operations
- Error classification

**Example Logs**:
```
WARNING - Circuit breaker state change: CLOSED → OPEN - Failure rate exceeded threshold (60.0%)
WARNING - TTS synthesis retry 2/3 - Error: RATE_LIMIT (429) - Backing off 2.1s
INFO - TTS recovery successful after 3 attempts
ERROR - TTS operation failed after 3 attempts - falling back to muted state
```

### Cache Operations

**Logger**: `utils.multi_tier_audio_cache`

**Key Events**:
- Cache initialization
- Entry storage and retrieval
- Eviction operations
- Performance statistics

**Example Logs**:
```
INFO - Multi-tier audio cache initialized: memory=100 entries, persistent=enabled
DEBUG - Cache hit for text hash: a1b2c3d4...
DEBUG - Evicted cache entry: e5f6g7h8...
DEBUG - Cached audio for text hash: i9j0k1l2... (size: 15234 bytes)
INFO - Audio cache cleared
```

## Monitoring and Analysis

### Performance Tracking

Monitor TTS performance through logs:

```bash
# Track synthesis times
grep "Successfully synthesized" logs/app.log | awk '{print $NF}' | sed 's/s$//'

# Monitor cache hit rate
grep -c "TTS cache hit" logs/app.log
grep -c "TTS cache miss" logs/app.log

# Track error rates
grep -c "TTS synthesis retry" logs/app.log
grep -c "Circuit breaker state change" logs/app.log
```

### Error Analysis

Analyze error patterns:

```bash
# API key errors
grep "API key error" logs/app.log

# Rate limiting issues
grep "Rate limited" logs/app.log

# Server errors
grep "Server error" logs/app.log

# Network problems
grep "Network error" logs/app.log
```

### Memory Usage Monitoring

Track memory consumption:

```bash
# Memory cleanup events
grep "Memory cleanup performed" logs/app.log

# Cache eviction patterns
grep "Evicted cache entry" logs/app.log

# Resource cleanup
grep "TTS service resources cleaned up" logs/app.log
```

## Log Rotation and Management

### File-based Logging

Configure log rotation for production:

```python
import logging.handlers
import gzip
import os

# Custom namer function to add .gz extension
def namer(name):
    return name + ".gz"

# Custom rotator function to compress rotated files
def rotator(source, dest):
    with open(source, "rb") as sf:
        with gzip.open(dest, "wb") as df:
            df.writelines(sf)
    os.remove(source)

# Time-based rotation with compression
handler = logging.handlers.TimedRotatingFileHandler(
    'logs/tts.log',
    when='midnight',
    interval=1,
    backupCount=7,
    encoding='utf-8',
    delay=True
)

# Enable compression for rotated files
handler.namer = namer
handler.rotator = rotator
```

### Structured Logging

For production monitoring, use structured logging:

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add TTS-specific fields
        if hasattr(record, 'synthesis_time'):
            log_entry['synthesis_time'] = record.synthesis_time
        if hasattr(record, 'cache_key'):
            log_entry['cache_key'] = record.cache_key
        if hasattr(record, 'error_code'):
            log_entry['error_code'] = record.error_code
            
        return json.dumps(log_entry)

# Usage example: Attach JSONFormatter to a handler
json_handler = logging.StreamHandler()
json_handler.setFormatter(JSONFormatter())

# Add the handler to the TTS service logger
tts_logger = logging.getLogger('utils.tts_service')
tts_logger.addHandler(json_handler)
tts_logger.setLevel(logging.INFO)

# Example log output (will be in JSON format)
tts_logger.info("TTS synthesis completed", extra={
    'synthesis_time': 1.23,
    'cache_key': 'hello_world_voice1'
})
```

## Troubleshooting with Logs

### Common Issues and Log Patterns

#### 1. API Key Problems

**Symptoms**: Voice functionality disabled
**Log Pattern**:
```
WARNING - ELEVEN_LABS_API_KEY not found in environment variables
ERROR - API key error detected - no retries will be attempted
```

**Solution**: Verify API key configuration

#### 2. Rate Limiting

**Symptoms**: Delayed or failed synthesis
**Log Pattern**:
```
WARNING - TTS synthesis retry 1/3 - Error: RATE_LIMIT (429) - Backing off 1.2s
WARNING - TTS synthesis retry 2/3 - Error: RATE_LIMIT (429) - Backing off 2.4s
```

**Solution**: Implement request throttling or upgrade API plan

#### 3. Memory Issues

**Symptoms**: Slow performance, high memory usage
**Log Pattern**:
```
DEBUG - Memory cleanup performed: {'cache_entries_removed': 25, 'temp_files_cleaned': 10}
DEBUG - Evicted cache entry: a1b2c3d4...
```

**Solution**: Adjust cache size or cleanup frequency

#### 4. Network Problems

**Symptoms**: Intermittent failures
**Log Pattern**:
```
WARNING - TTS recovery check failed - Status: 503, Attempt: 2
ERROR - Network error retries exhausted after 3 attempts
```

**Solution**: Check network connectivity and ElevenLabs service status

### Debug Mode

Enable comprehensive debugging:

```bash
export LOG_LEVEL=DEBUG
export TTS_DEBUG=1
python launch_bitcoin_assistant.py
```

This provides detailed information about:
- API request/response details
- Cache operations and statistics
- Circuit breaker state transitions
- Memory usage patterns
- Performance metrics

## Integration with Monitoring Systems

### Prometheus Metrics

Export TTS metrics for monitoring:

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
tts_requests_total = Counter('tts_requests_total', 'Total TTS requests')
tts_synthesis_duration = Histogram('tts_synthesis_duration_seconds', 'TTS synthesis time')
tts_cache_hit_ratio = Gauge('tts_cache_hit_ratio', 'Cache hit ratio')
tts_error_rate = Gauge('tts_error_rate', 'Error rate percentage')

# Update metrics in code
tts_requests_total.inc()
tts_synthesis_duration.observe(synthesis_time)
```

### ELK Stack Integration

Configure for Elasticsearch, Logstash, and Kibana:

```json
{
  "version": "1",
  "disable_existing_loggers": false,
  "formatters": {
    "elk": {
      "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
    }
  },
  "handlers": {
    "elk": {
      "class": "logging.handlers.SysLogHandler",
      "address": ["logstash-host", 5000],
      "formatter": "elk"
    }
  },
  "loggers": {
    "utils.tts_service": {
      "handlers": ["elk"],
      "level": "INFO"
    }
  }
}
```

## Best Practices

### Development

1. **Use DEBUG level** for detailed troubleshooting
2. **Log entry and exit** of major operations
3. **Include context** in log messages (user ID, request ID)
4. **Avoid logging sensitive data** (API keys, personal info)

### Production

1. **Use INFO or WARNING level** to reduce noise
2. **Implement log aggregation** for multiple instances
3. **Set up alerting** for ERROR and CRITICAL events
4. **Monitor log volume** to prevent disk space issues

### Performance

1. **Use lazy evaluation** for expensive log formatting
2. **Implement sampling** for high-frequency events
3. **Buffer log writes** for better I/O performance
4. **Compress rotated logs** to save space

## Security Considerations

### Sensitive Data

Never log:
- API keys or authentication tokens
- User personal information
- Full response content (may contain sensitive data)
- Internal system details that could aid attackers

### Log Access

- Restrict log file access to authorized personnel
- Use secure log transmission (TLS)
- Implement log integrity checking
- Regular log retention and secure deletion

### Audit Trail

Maintain audit logs for:
- API key usage and rotation
- Configuration changes
- Error patterns and responses
- Performance anomalies