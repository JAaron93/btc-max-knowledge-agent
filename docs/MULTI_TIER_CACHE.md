# Multi-Tier Audio Cache System

The multi-tier audio cache system provides comprehensive caching for TTS responses with support for memory, persistent, and distributed storage backends.

## Features

- **Multi-tier architecture**: Memory → Persistent → Distributed → API call
- **Multiple backends**: SQLite, Redis, and in-memory caching
- **TTL support**: Automatic expiration with 24-hour default
- **Cache warming**: Preload frequently accessed content
- **Comprehensive statistics**: Performance metrics across all tiers
- **Thread-safe**: Concurrent access support
- **Retry logic**: Exponential backoff for API rate limits and errors

## Configuration

Configure the cache system using environment variables:

```bash
# Cache backend selection
CACHE_BACKEND=multi-tier  # Options: memory, sqlite, redis, multi-tier

# Memory cache settings
CACHE_MEMORY_MAX_SIZE=100
CACHE_MEMORY_MAX_MB=50

# Persistent cache settings
CACHE_PERSISTENT_PATH=./cache
CACHE_PERSISTENT_MAX_SIZE=1000
CACHE_PERSISTENT_MAX_MB=500

# TTL and cleanup settings
CACHE_TTL_HOURS=24
CACHE_CLEANUP_INTERVAL_MINUTES=60

# Optional Redis settings (for distributed caching)
CACHE_REDIS_HOST=localhost
CACHE_REDIS_PORT=6379
CACHE_REDIS_DB=0
CACHE_REDIS_PASSWORD=your_password
CACHE_REDIS_MAX_CONNECTIONS=10

# Feature toggles
CACHE_ENABLE_WARMING=true
CACHE_ENABLE_STATISTICS=true
```

## Usage

### Basic Usage

```python
from utils.multi_tier_audio_cache import get_audio_cache

# Get global cache instance
cache = get_audio_cache()

# Store audio data
text = "Hello, this is a test message"
audio_data = b"fake_audio_data"
cache_key = cache.put(text, audio_data)

# Retrieve audio data
retrieved_audio = cache.get(text)

# Check if cached
if cache.has(text):
    print("Text is cached")

# Remove from cache
cache.remove(text)

# Clear all cache tiers
cache.clear()
```

### Advanced Usage

```python
from utils.multi_tier_audio_cache import MultiTierAudioCache, CacheConfig

# Custom configuration
config = CacheConfig(
    backend="multi-tier",
    memory_max_size=200,
    memory_max_mb=100,
    persistent_path="./custom_cache",
    ttl_hours=48
)

# Initialize with custom config
cache = MultiTierAudioCache(config)

# Cache warming
warm_entries = [
    ("Frequently used text 1", b"audio_data_1"),
    ("Frequently used text 2", b"audio_data_2")
]
warmed_count = cache.warm_cache(warm_entries)

# Get comprehensive statistics
stats = cache.get_comprehensive_stats()
print(f"Memory hit rate: {stats['performance']['memory_hit_rate']:.2%}")
print(f"Total entries: {stats['backends']['memory']['entry_count']}")

# Manual cleanup
cleanup_results = cache.cleanup_expired()
print(f"Cleaned up: {cleanup_results}")
```

### TTS Service Integration

```python
from utils.tts_service import TTSService, TTSConfig

# TTS service automatically uses multi-tier cache
tts_config = TTSConfig(api_key="your_api_key")
tts_service = TTSService(tts_config)

# Synthesize text (uses cache automatically)
audio_data = await tts_service.synthesize_text("Hello world")

# Get cache statistics
cache_stats = tts_service.get_cache_stats()

# Warm cache with common phrases
common_phrases = [
    ("Welcome to Bitcoin Assistant", b"welcome_audio"),
    ("How can I help you today?", b"help_audio")
]
tts_service.warm_cache(common_phrases)
```

## Cache Backends

### Memory Cache
- **Fastest access** (microseconds)
- **LRU eviction** policy
- **Size and memory limits**
- **TTL support** with automatic cleanup
- **Thread-safe** operations

### SQLite Cache (Persistent)
- **Survives restarts** and crashes
- **BLOB storage** for audio data
- **Automatic cleanup** of expired entries
- **Size management** with LRU eviction
- **No external dependencies**

### Redis Cache (Distributed)
- **Cluster-wide sharing** across instances
- **High performance** with sub-millisecond access
- **Built-in TTL** and expiration
- **Configurable eviction** policies
- **Graceful fallback** if unavailable

## Cache Hierarchy

The system uses a hierarchical approach for optimal performance:

1. **Memory Cache**: Check first for fastest access
2. **Persistent Cache**: Check if not in memory, warm memory on hit
3. **Distributed Cache**: Check if not in persistent, warm lower tiers on hit
4. **API Call**: If not cached anywhere, synthesize and cache in all tiers

## Performance Characteristics

| Operation | Memory | SQLite | Redis |
|-----------|--------|--------|-------|
| Get (hit) | ~0.01ms | ~1-5ms | ~0.1-1ms |
| Put | ~0.01ms | ~5-10ms | ~0.5-2ms |
| Has | ~0.01ms | ~1-3ms | ~0.1-0.5ms |
| Cleanup | ~1ms | ~10-50ms | Automatic |

## Monitoring and Statistics

### Performance Metrics
- **Hit rates** per cache tier
- **Request counts** (hits, misses, puts, errors)
- **Response times** and latency
- **Cache size** and memory usage

### Backend Statistics
- **Entry counts** and total size
- **Access patterns** and frequency
- **Expiration** and cleanup metrics
- **Error rates** and availability

### Example Statistics Output

```json
{
  "config": {
    "backend": "multi-tier",
    "memory_max_size": 100,
    "ttl_hours": 24
  },
  "performance": {
    "hits": {"memory": 150, "persistent": 25, "distributed": 5},
    "misses": {"memory": 30, "persistent": 20, "distributed": 15},
    "memory_hit_rate": 0.833,
    "persistent_hit_rate": 0.556,
    "distributed_hit_rate": 0.250
  },
  "backends": {
    "memory": {
      "backend_type": "memory",
      "entry_count": 85,
      "total_size_bytes": 2048576,
      "memory_usage_percent": 78.5
    },
    "persistent": {
      "backend_type": "sqlite",
      "entry_count": 450,
      "total_size_bytes": 15728640,
      "db_path": "./cache/audio_cache.db"
    }
  }
}
```

## Error Handling and Retry Logic

The system includes robust error handling with exponential backoff:

### Rate Limiting (HTTP 429)
- **Max retries**: 3 attempts
- **Base delay**: 1 second
- **Max delay**: 16 seconds
- **Exponential backoff**: 1s → 2s → 4s → 8s → 16s

### Server Errors (HTTP 5xx)
- **Max retries**: 2 attempts
- **Base delay**: 0.5 seconds
- **Max delay**: 8 seconds
- **Exponential backoff**: 0.5s → 1s → 2s → 4s → 8s

### Jitter
- **Random delay**: ±25% of calculated backoff
- **Prevents thundering herd** effect
- **Improves system stability** under load

## Best Practices

### Configuration
- Use **multi-tier** backend for production
- Set appropriate **memory limits** based on available RAM
- Configure **TTL** based on content freshness requirements
- Enable **cache warming** for frequently accessed content

### Performance
- **Warm cache** with common phrases during startup
- **Monitor hit rates** and adjust cache sizes accordingly
- **Use Redis** for distributed deployments
- **Regular cleanup** to prevent unbounded growth

### Monitoring
- **Track cache statistics** for performance optimization
- **Monitor error rates** and retry patterns
- **Set up alerts** for cache availability issues
- **Log cache operations** for debugging

### Deployment
- **Persistent storage** should be on fast SSD
- **Redis instance** should have sufficient memory
- **Network latency** affects distributed cache performance
- **Backup strategies** for persistent cache data

## Troubleshooting

### Common Issues

1. **High memory usage**
   - Reduce `CACHE_MEMORY_MAX_MB`
   - Increase cleanup frequency
   - Check for memory leaks

2. **Poor hit rates**
   - Increase cache sizes
   - Extend TTL duration
   - Implement cache warming

3. **Redis connection errors**
   - Check Redis server availability
   - Verify connection parameters
   - Enable graceful fallback

4. **SQLite lock errors**
   - Reduce concurrent access
   - Check disk space
   - Verify file permissions

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('utils.multi_tier_audio_cache').setLevel(logging.DEBUG)
logging.getLogger('utils.tts_service').setLevel(logging.DEBUG)
```

## Testing

Run the comprehensive test suite:

```bash
# Run all cache tests
python -m pytest tests/test_multi_tier_cache.py -v

# Run integration tests
python examples/test_multi_tier_cache.py

# Run with coverage
python -m pytest tests/test_multi_tier_cache.py --cov=utils.multi_tier_audio_cache
```

## Migration from Simple Cache

If upgrading from the simple in-memory cache:

1. **Update environment variables** to use multi-tier backend
2. **Existing code** continues to work without changes
3. **Cache data** will be automatically migrated to new format
4. **Performance improvements** are immediate

The multi-tier cache is fully backward compatible with the existing TTS service API.