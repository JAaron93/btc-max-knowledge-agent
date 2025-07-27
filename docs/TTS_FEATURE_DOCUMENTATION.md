# TTS Feature Technical Documentation

## Architecture Overview

The Text-to-Speech (TTS) feature is built as a modular system that integrates with the existing Bitcoin Knowledge Assistant. It provides real-time speech synthesis using the ElevenLabs API with comprehensive caching, error handling, and user controls.

### Core Components

```
TTS System Architecture
├── TTS Service (src/utils/tts_service.py)
│   ├── Speech synthesis coordination
│   ├── Connection pooling
│   ├── Memory management
│   └── Performance monitoring
├── Audio Cache (src/utils/multi_tier_audio_cache.py)
│   ├── Multi-tier caching strategy
│   ├── LRU eviction policies
│   └── Persistent storage
├── Error Handler (src/utils/tts_error_handler.py)
│   ├── Circuit breaker pattern
│   ├── Exponential backoff retry
│   └── Recovery mechanisms
├── Audio Utils (src/utils/audio_utils.py)
│   ├── Content extraction
│   ├── Audio format handling
│   └── Streaming utilities
└── UI Integration (src/web/bitcoin_assistant_ui.py)
    ├── Voice controls
    ├── Visual feedback
    └── Audio streaming
```

## Configuration

### Environment Variables

The TTS feature is configured through environment variables:

```bash
# Required
ELEVEN_LABS_API_KEY=your_api_key_here

# Optional (with defaults)
TTS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
TTS_MODEL_ID=eleven_multilingual_v2
TTS_OUTPUT_FORMAT=mp3_44100_128
TTS_VOLUME=0.7
TTS_CACHE_SIZE=100
LOG_LEVEL=INFO
```

### TTSConfig Class

The main configuration is handled by the `TTSConfig` dataclass:

**Note**: Environment variables map directly to dataclass fields with the `TTS_` prefix. For example, `TTS_VOLUME` maps to the `volume` field, `TTS_VOICE_ID` maps to `voice_id`, etc.

```python
@dataclass
class TTSConfig:
    api_key: str                              # ElevenLabs API key
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # Voice identifier
    model_id: str = "eleven_multilingual_v2"  # TTS model
    output_format: str = "mp3_44100_128"      # Audio format
    enabled: bool = True                      # Feature enabled
    volume: float = 0.7                       # Default volume (0.0-1.0)
    cache_size: int = 100                     # Cache entry limit
```

### Cache Configuration

Multi-tier caching is configured through `CacheConfig`:

```python
@dataclass
class CacheConfig:
    memory_cache_size: int = 100              # In-memory entries
    memory_cache_max_size_mb: int = 50        # Memory limit (MB)
    persistent_cache_enabled: bool = True     # Enable disk cache
    persistent_cache_ttl_hours: int = 24      # Time-to-live
    distributed_cache_enabled: bool = False   # Redis cache
    cleanup_interval_minutes: int = 30        # Cleanup frequency
```

## API Integration

### ElevenLabs API Usage

The system integrates with ElevenLabs API endpoints:

#### Text-to-Speech Synthesis
```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
```

**Request Headers:**
```
Accept: audio/mpeg
xi-api-key: {api_key}
Content-Type: application/json
```

**Request Body:**
```json
{
  "text": "cleaned_response_text",
  "model_id": "eleven_multilingual_v2",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.5
  }
}
```

**Response:**
- Content-Type: `audio/mpeg`
- Body: MP3 audio data

### Connection Pooling

The system uses aiohttp connection pooling for optimal performance:

```python
import aiohttp
class ConnectionPool:
    def __init__(self, max_connections: int = 10, connection_timeout: float = 10.0):
        self.connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=max_connections,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        self.timeout = aiohttp.ClientTimeout(
            total=45,
            connect=connection_timeout,
            sock_read=30
        )
```

## Caching System

### Multi-Tier Architecture

The caching system implements a three-tier strategy:

1. **Memory Cache (L1)**: Fast in-memory LRU cache
2. **Persistent Cache (L2)**: Disk-based storage with TTL
3. **Distributed Cache (L3)**: Redis for horizontal scaling (optional)

### Cache Key Generation

Cache keys are generated using SHA-256 hashing of cleaned text:

```python
def _generate_cache_key(self, text: str) -> str:
    """Generate SHA-256 hash for cache key."""
    cleaned_text = self._clean_text_for_synthesis(text)
    return hashlib.sha256(cleaned_text.encode('utf-8')).hexdigest()
```

### Cache Entry Structure

```python
@dataclass
class CacheEntry:
    text_hash: str          # SHA-256 hash of original text
    audio_data: bytes       # MP3 audio data
    timestamp: datetime     # Creation time
    access_count: int       # Usage frequency
    size_bytes: int         # Memory footprint
    ttl_hours: int = 24     # Time-to-live
```

### Eviction Policies

- **LRU (Least Recently Used)**: Primary eviction strategy
- **Size-based**: Evict when cache exceeds memory limits
- **TTL-based**: Remove expired entries during cleanup
- **Access-based**: Prioritize frequently accessed content

## Error Handling

### Circuit Breaker Pattern

The system implements a circuit breaker to handle API failures:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: float = 0.5, window_size: int = 10, 
                 cooldown_period: int = 60):
        self.failure_threshold = failure_threshold    # 50% failure rate
        self.window_size = window_size               # Last 10 requests
        self.cooldown_period = cooldown_period       # 60 second cooldown
```

**States:**
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Circuit tripped, requests fail immediately
- **HALF_OPEN**: Testing recovery, limited requests allowed

### Retry Strategy

Exponential backoff with jitter for different error types:

#### Rate Limiting (HTTP 429)
- Initial delay: 1 second
- Maximum delay: 16 seconds
- Maximum retries: 3
- Jitter: ±25%

#### Server Errors (HTTP 5xx)
- Initial delay: 0.5 seconds
- Maximum delay: 8 seconds
- Maximum retries: 2
- Jitter: ±25%

#### Timeout Handling
- Connection timeout: 10 seconds
- Read timeout: 30 seconds
- Total timeout: 45 seconds

### Error Classification

```python
class TTSError(Exception):
    """Base TTS error with error codes."""
    
class TTSAPIKeyError(TTSError):
    """API key missing or invalid."""
    
class TTSRateLimitError(TTSError):
    """Rate limit exceeded."""
    
class TTSServerError(TTSError):
    """ElevenLabs server error."""
    
class TTSNetworkError(TTSError):
    """Network connectivity issues."""
    
class TTSRetryExhaustedError(TTSError):
    """All retry attempts failed."""
```

## Content Processing

### Text Cleaning Algorithm

The system applies a standardized text cleaning process:

1. **Markdown Removal**: Strip formatting (`**bold**`, `*italic*`, etc.)
2. **HTML Cleaning**: Remove tags and entities
3. **Citation Removal**: Filter source references and citations
4. **URL Removal**: Strip web addresses and email addresses
5. **Character Conversion**: Convert symbols to speech-friendly text
6. **Whitespace Normalization**: Collapse multiple spaces
7. **Length Validation**: Ensure content within API limits

```python
import re
import unicodedata

def _clean_markdown(text: str) -> str:
    """
    Remove markdown formatting for TTS-friendly text.
    
    Handles common markdown syntax like bold, italic, headers, links, etc.
    """
    # Remove headers (# ## ### etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Remove bold and italic formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic*
    text = re.sub(r'__([^_]+)__', r'\1', text)      # __bold__
    text = re.sub(r'_([^_]+)_', r'\1', text)        # _italic_
    
    # Remove links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # [text](url)
    text = re.sub(r'<([^>]+)>', r'\1', text)              # <url>
    
    # Remove code blocks and inline code
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)  # ```code```
    text = re.sub(r'`([^`]+)`', r'\1', text)                  # `code`
    
    # Remove list markers
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)  # - * +
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE) # 1. 2. 3.
    
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    
    return text

def _normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace and unicode characters for consistent TTS output.
    
    Handles multiple spaces, line breaks, and unicode normalization.
    """
    # Normalize unicode characters (NFD -> NFC)
    text = unicodedata.normalize('NFC', text)
    
    # Replace multiple whitespace characters with single spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace from each line
    text = '\n'.join(line.strip() for line in text.split('\n'))
    
    # Collapse multiple newlines into single newlines
    text = re.sub(r'\n\s*\n', '\n', text)
    
    # Final cleanup: strip and ensure single spaces
    text = text.strip()
    text = re.sub(r' +', ' ', text)
    
    return text

def extract_main_content(response_text: str) -> str:
    """Extract clean content for TTS synthesis."""
    # Pre-compiled regex patterns for performance
    MULTILINE_SOURCE_PATTERNS = [
        re.compile(r'\n\s*\*\*Sources?\*\*.*$', re.MULTILINE | re.DOTALL | re.IGNORECASE),
        re.compile(r'\n\s*##\s*Sources?.*$', re.MULTILINE | re.DOTALL | re.IGNORECASE),
        # ... additional patterns
    ]
    
    # Apply cleaning steps
    clean_text = response_text.strip()
    clean_text = _clean_markdown(clean_text)
    
    for pattern in MULTILINE_SOURCE_PATTERNS:
        clean_text = pattern.sub('', clean_text)
    
    return _normalize_whitespace(clean_text)
```

### Character Limits

- **ElevenLabs Limit**: 2,500 characters per request
- **Truncation Strategy**: Preserve sentence boundaries
- **Fallback Message**: "No content available for synthesis."

## Performance Monitoring

### Metrics Tracking

The system tracks comprehensive performance metrics:

```python
@dataclass
class PerformanceStats:
    synthesis_times: List[float]      # Response time history
    cache_hits: int                   # Cache hit count
    cache_misses: int                 # Cache miss count
    memory_cleanups: int              # Cleanup operations
    api_calls: int                    # Total API requests
    error_count: int                  # Error occurrences
    circuit_breaker_trips: int        # Circuit breaker activations
```

### Memory Management

Automatic memory monitoring and cleanup:

```python
class MemoryMonitor:
    def __init__(self, cleanup_threshold_mb: int = 100, 
                 cleanup_interval_minutes: int = 30):
        self.cleanup_threshold_mb = cleanup_threshold_mb
        self.cleanup_interval_minutes = cleanup_interval_minutes
    
    def should_cleanup(self) -> bool:
        """Check if memory cleanup is needed."""
        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
        return memory_usage > self.cleanup_threshold_mb
```

## User Interface Integration

### Gradio Components

The TTS feature integrates with Gradio through custom components:

```python
# Voice controls
voice_enabled = gr.Checkbox(
    label="Enable Voice",
    value=True,
    info="Toggle text-to-speech functionality"
)

voice_volume = gr.Slider(
    minimum=0,
    maximum=100,
    value=70,
    step=5,
    label="Voice Volume",
    info="Adjust audio playback volume"
)

# Audio output
audio_output = gr.Audio(
    label="Response Audio",
    autoplay=True,
    streaming=True,
    show_download_button=False
)
```

### Visual Feedback

Waveform animation during synthesis:

```python
def create_waveform_animation():
    """Create animated waveform during TTS synthesis."""
    return gr.HTML(
        value="""
        <div class="waveform-container" style="display: none;">
            <div class="waveform-bar"></div>
            <div class="waveform-bar"></div>
            <div class="waveform-bar"></div>
        </div>
        """,
        visible=False
    )
```

### Error Indicators

Visual error feedback system:

```python
def create_error_indicator(error_type: str, consecutive_failures: int) -> gr.HTML:
    """Create error indicator HTML component."""
    import gradio as gr
    
    error_configs = {
        "API_KEY_ERROR": {
            "icon": "🔴",
            "message": "Invalid API key - Voice disabled",
            "color": "#dc2626"
        },
        "RATE_LIMIT": {
            "icon": "🟡", 
            "message": "Rate limited - Retrying automatically",
            "color": "#f59e0b"
        },
        "NETWORK_ERROR": {
            "icon": "🟠",
            "message": f"Network error - {consecutive_failures} consecutive failures",
            "color": "#ea580c"
        },
        "QUOTA_EXCEEDED": {
            "icon": "🔴",
            "message": "Quota exceeded - Voice temporarily disabled",
            "color": "#dc2626"
        }
    }
    
    config = error_configs.get(error_type, {
        "icon": "⚠️",
        "message": f"Unknown error - {consecutive_failures} failures",
        "color": "#6b7280"
    })
    
    html_content = f"""
    <div style="
        display: flex;
        align-items: center;
        padding: 8px 12px;
        background-color: {config['color']}15;
        border: 1px solid {config['color']};
        border-radius: 6px;
        margin: 4px 0;
        font-size: 14px;
        color: {config['color']};
    ">
        <span style="margin-right: 8px; font-size: 16px;">{config['icon']}</span>
        <span>{config['message']}</span>
    </div>
    """
    
    return gr.HTML(value=html_content)
```

## Testing Strategy

### Unit Tests

Comprehensive test coverage for all components:

```python
class TestTTSService:
    def test_synthesis_success(self):
        """Test successful TTS synthesis."""
        
    def test_cache_hit_miss(self):
        """Test cache behavior."""
        
    def test_error_handling(self):
        """Test error scenarios."""
        
    def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
```

### Integration Tests

End-to-end testing scenarios:

```python
class TestTTSIntegration:
    def test_query_to_audio_flow(self):
        """Test complete query-to-audio pipeline."""
        
    def test_ui_controls_integration(self):
        """Test UI control functionality."""
        
    def test_error_recovery(self):
        """Test error recovery mechanisms."""
```

### Load Testing

Performance validation under stress:

```python
class TestTTSPerformance:
    def test_concurrent_synthesis(self):
        """Test 100 concurrent synthesis requests."""
        
    def test_memory_usage(self):
        """Test memory consumption patterns."""
        
    def test_cache_performance(self):
        """Test cache efficiency under load."""
```

## Deployment Considerations

### Production Configuration

Recommended production settings:

```bash
# Performance
TTS_CACHE_SIZE=500
LOG_LEVEL=WARNING

# Reliability
CIRCUIT_BREAKER_THRESHOLD=0.3
RETRY_MAX_ATTEMPTS=5

# Resource Management
MEMORY_CLEANUP_THRESHOLD_MB=200
CONNECTION_POOL_SIZE=20
```

### Monitoring and Alerting

Key metrics to monitor in production:

- **API Response Times**: Track synthesis latency
- **Error Rates**: Monitor failure percentages
- **Cache Hit Ratio**: Optimize for cost efficiency
- **Memory Usage**: Prevent resource exhaustion
- **Circuit Breaker State**: Track service health

### Scaling Considerations

For high-traffic deployments:

1. **Horizontal Scaling**: Multiple application instances
2. **Distributed Caching**: Redis cluster for shared cache
3. **Load Balancing**: Distribute TTS requests
4. **API Rate Management**: Coordinate rate limits across instances

## Security

### API Key Management

- Store keys in environment variables only
- Use key rotation policies
- Monitor API usage for anomalies
- Implement access logging

### Content Security

- Sanitize text before API transmission
- Validate audio data integrity
- Implement content filtering if needed
- Log synthesis requests for audit

### Network Security

- Use HTTPS for all API communications
- Implement request signing if available
- Monitor for unusual traffic patterns
- Use connection timeouts to prevent hangs

## Troubleshooting

### Common Issues

#### High Memory Usage
- Check cache size configuration
- Monitor cleanup frequency
- Verify eviction policies
- Consider distributed caching

#### Slow Response Times
- Check network connectivity
- Monitor ElevenLabs service status
- Optimize cache hit rates
- Review connection pool settings

#### Frequent Errors
- Verify API key validity
- Check rate limit settings
- Monitor circuit breaker state
- Review retry configuration

### Debug Logging

Enable detailed logging for troubleshooting:

```python
import logging
logging.getLogger('src.utils.tts_service').setLevel(logging.DEBUG)
logging.getLogger('src.utils.tts_error_handler').setLevel(logging.DEBUG)
logging.getLogger('src.utils.multi_tier_audio_cache').setLevel(logging.DEBUG)
logging.getLogger('src.utils.audio_utils').setLevel(logging.DEBUG)
```

### Performance Profiling

Use built-in performance monitoring:

```python
# Get performance statistics
stats = tts_service.get_performance_stats()
cache_stats = tts_service.get_cache_stats()

# Monitor memory usage
memory_info = tts_service.memory_monitor.get_memory_info()
```

## Future Enhancements

### Planned Features

- **Voice Customization**: User-selectable voices
- **Streaming Synthesis**: Real-time audio generation
- **Offline Mode**: Local TTS fallback
- **Multi-language Support**: Language detection and voice matching
- **Custom Voice Training**: Personalized voice models

### API Improvements

- **Batch Processing**: Multiple text synthesis
- **Voice Cloning**: Custom voice creation
- **Real-time Streaming**: WebSocket-based synthesis
- **Advanced Controls**: Pitch, speed, emotion controls

### Performance Optimizations

- **Predictive Caching**: Pre-generate common responses
- **Compression**: Optimize audio storage
- **CDN Integration**: Distribute cached audio
- **Edge Computing**: Reduce latency with edge synthesis