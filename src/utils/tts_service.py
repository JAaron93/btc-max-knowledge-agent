"""
Text-to-Speech service using ElevenLabs API with multi-tier caching and comprehensive error handling.
"""

import asyncio
import gc
import hashlib
import logging
import os
import threading
import time
import weakref
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp
import psutil

try:  # Prefer external util, fall back to local copy when running inside the repo
    from btc_max_knowledge_agent.utils.validation import validate_volume_strict
except ImportError:  # pragma: no cover
    from .validation import validate_volume_strict
from .multi_tier_audio_cache import CacheConfig, get_audio_cache
from .tts_error_handler import (
    TTSAPIKeyError,
    TTSError,
    TTSNetworkError,
    TTSRateLimitError,
    TTSRetryExhaustedError,
    TTSServerError,
    get_tts_error_handler,
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class TTSConfig:
    """Configuration for TTS service."""

    api_key: str
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # Default ElevenLabs voice
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"
    enabled: bool = True
    volume: float = 0.7  # Volume level (0.0 to 1.0)
    cache_size: int = 100

    def __post_init__(self):
        """Validate configuration values."""
        if not 0.0 <= self.volume <= 1.0:
            raise ValueError(f"Volume must be between 0.0 and 1.0, got {self.volume}")
        if self.cache_size < 0:
            raise ValueError(f"Cache size must be non-negative, got {self.cache_size}")


@dataclass
class CacheEntry:
    """Cache entry for storing audio data."""

    text_hash: str
    audio_data: bytes
    timestamp: datetime
    access_count: int
    size_bytes: int


# TTSError and related exceptions are now imported from tts_error_handler


class AudioCache:
    """In-memory LRU cache for generated audio."""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.total_size = 0

    def get(self, text_hash: str) -> Optional[bytes]:
        """Get cached audio data."""
        if text_hash in self.cache:
            entry = self.cache[text_hash]
            entry.access_count += 1
            # Move to end (most recently used)
            self.cache.move_to_end(text_hash)
            logger.debug(f"Cache hit for text hash: {text_hash[:8]}...")
            return entry.audio_data

        logger.debug(f"Cache miss for text hash: {text_hash[:8]}...")
        return None

    def put(self, text_hash: str, audio_data: bytes) -> None:
        """Store audio data in cache."""
        size_bytes = len(audio_data)

        # Remove existing entry if present
        if text_hash in self.cache:
            old_entry = self.cache[text_hash]
            self.total_size -= old_entry.size_bytes
            del self.cache[text_hash]

        # Create new entry
        entry = CacheEntry(
            text_hash=text_hash,
            audio_data=audio_data,
            timestamp=datetime.now(timezone.utc),
            access_count=1,
            size_bytes=size_bytes,
        )

        # Add to cache
        self.cache[text_hash] = entry
        self.total_size += size_bytes

        # Evict oldest entries if necessary
        while len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            oldest_entry = self.cache[oldest_key]
            self.total_size -= oldest_entry.size_bytes
            del self.cache[oldest_key]
            logger.debug(f"Evicted cache entry: {oldest_key[:8]}...")

        logger.debug(
            f"Cached audio for text hash: {text_hash[:8]}... (size: {size_bytes} bytes)"
        )

    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()
        self.total_size = 0
        logger.info("Audio cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "entries": len(self.cache),
            "total_size_bytes": self.total_size,
            "max_size": self.max_size,
        }


class ConnectionPool:
    """Connection pool for ElevenLabs API requests with automatic cleanup."""

    def __init__(
        self,
        max_connections: int = 10,
        connection_timeout: float = 10.0,
        read_timeout: float = 30.0,
        total_timeout: float = 45.0,
        cleanup_interval: int = 300,
    ):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.total_timeout = total_timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._connection_count = 0
        self._last_cleanup = time.time()
        self._cleanup_interval = (
            cleanup_interval  # Configurable cleanup interval in seconds
        )

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create a connection session with connection pooling."""
        async with self._lock:
            # Cleanup old connections periodically
            current_time = time.time()
            if current_time - self._last_cleanup > self._cleanup_interval:
                await self._cleanup_connections()
                self._last_cleanup = current_time

            if self._session is None or self._session.closed:
                # Create connector with connection pooling
                connector = aiohttp.TCPConnector(
                    limit=self.max_connections,
                    limit_per_host=self.max_connections,
                    ttl_dns_cache=300,  # DNS cache TTL
                    use_dns_cache=True,
                    keepalive_timeout=60,  # Keep connections alive for 60 seconds
                    enable_cleanup_closed=True,
                )

                # Create timeout configuration
                timeout = aiohttp.ClientTimeout(
                    connect=self.connection_timeout,
                    sock_read=self.read_timeout,
                    total=self.total_timeout,
                )

                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={
                        "User-Agent": "BTC-Knowledge-Agent/1.0",
                        "Connection": "keep-alive",
                    },
                )

                logger.debug(
                    f"Created new connection pool with {self.max_connections} max connections"
                )

            return self._session

    async def _cleanup_connections(self):
        """Clean up old connections."""
        if self._session and not self._session.closed:
            try:
                # Let aiohttp handle connection cleanup based on TTL and keepalive settings
                logger.debug("Connection cleanup check completed")
            except Exception as e:
                logger.warning(f"Error during connection cleanup: {e}")

    async def close(self):
        """Close the connection pool."""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                logger.debug("Connection pool closed")

    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        if self._session and not self._session.closed:
            connector = self._session.connector
            try:
                active_conns = (
                    len(connector._conns) if hasattr(connector, "_conns") else 0
                )
            except AttributeError:
                active_conns = 0
            return {
                "max_connections": self.max_connections,
                "active_connections": active_conns,
                "available_connections": connector.limit - active_conns,
                "session_closed": self._session.closed,
                "last_cleanup": self._last_cleanup,
            }
        return {
            "max_connections": self.max_connections,
            "active_connections": 0,
            "available_connections": self.max_connections,
            "session_closed": True,
            "last_cleanup": self._last_cleanup,
        }


class MemoryMonitor:
    """Monitor and manage memory usage for audio cache and TTS operations."""

    def __init__(self, max_memory_mb: int = 100, cleanup_threshold: float = 0.8):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cleanup_threshold = cleanup_threshold
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # 1 minute
        self._temp_files: weakref.WeakSet = weakref.WeakSet()

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            return {
                "rss_bytes": memory_info.rss,
                "vms_bytes": memory_info.vms,
                "rss_mb": memory_info.rss / (1024 * 1024),
                "vms_mb": memory_info.vms / (1024 * 1024),
                "memory_percent": process.memory_percent(),
                "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
                "cleanup_threshold": self.cleanup_threshold,
            }
        except ImportError:
            # Fallback if psutil is not available
            return {
                "rss_bytes": 0,
                "vms_bytes": 0,
                "rss_mb": 0,
                "vms_mb": 0,
                "memory_percent": 0,
                "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
                "cleanup_threshold": self.cleanup_threshold,
                "note": "psutil not available - install with: pip install psutil",
            }

    def should_cleanup(self) -> bool:
        """Check if memory cleanup is needed."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return False

        try:
            process = psutil.Process(os.getpid())
            memory_percent = process.memory_percent()

            # Trigger cleanup if memory usage exceeds threshold
            return memory_percent > (self.cleanup_threshold * 100)
        except ImportError:
            # Without psutil, use time-based cleanup
            return True

    def cleanup_memory(self, cache_instance=None) -> Dict[str, int]:
        """Perform memory cleanup operations."""
        with self._lock:
            cleanup_results = {
                "cache_entries_removed": 0,
                "temp_files_cleaned": 0,
                "gc_collected": 0,
            }

            # Clean up cache if provided
            if cache_instance:
                try:
                    expired_count = cache_instance.cleanup_expired()

                    # Validate and safely handle the return type
                    if isinstance(expired_count, dict):
                        # If dict, sum all values (assuming they're numeric)
                        try:
                            cleanup_results["cache_entries_removed"] = sum(
                                expired_count.values()
                            )
                        except (TypeError, ValueError) as e:
                            logger.warning(
                                f"Invalid dict values in cleanup_expired result: {e}"
                            )
                            cleanup_results["cache_entries_removed"] = 0
                    elif isinstance(expired_count, int):
                        # If integer, use directly
                        cleanup_results["cache_entries_removed"] = expired_count
                    elif expired_count is None:
                        # Handle None return gracefully
                        logger.debug(
                            "cleanup_expired returned None, assuming 0 entries removed"
                        )
                        cleanup_results["cache_entries_removed"] = 0
                    else:
                        # Handle unexpected types
                        logger.warning(
                            f"Unexpected return type from cleanup_expired: {type(expired_count)}. "
                            f"Expected dict or int, got {expired_count}. Using default value 0."
                        )
                        cleanup_results["cache_entries_removed"] = 0

                except Exception as e:
                    logger.warning(f"Cache cleanup failed: {e}")
                    cleanup_results["cache_entries_removed"] = 0

            # Clean up temporary files
            temp_files_cleaned = 0
            for temp_file in list(self._temp_files):
                try:
                    if hasattr(temp_file, "cleanup") and callable(temp_file.cleanup):
                        temp_file.cleanup()
                        temp_files_cleaned += 1
                except Exception as e:
                    logger.debug(f"Temp file cleanup failed: {e}")

            cleanup_results["temp_files_cleaned"] = temp_files_cleaned

            # Force garbage collection
            cleanup_results["gc_collected"] = gc.collect()

            self._last_cleanup = time.time()

            logger.info(f"Memory cleanup completed: {cleanup_results}")
            return cleanup_results

    def register_temp_file(self, temp_file):
        """Register a temporary file for cleanup."""
        self._temp_files.add(temp_file)


class TTSService:
    """Text-to-Speech service with ElevenLabs integration, connection pooling, and memory management."""

    def __init__(
        self,
        config: Optional[TTSConfig] = None,
        cache_config: Optional[CacheConfig] = None,
    ):
        """Initialize TTS service with performance optimizations."""
        if config is None:
            api_key = os.getenv("ELEVEN_LABS_API_KEY")
            if not api_key:
                logger.warning("ELEVEN_LABS_API_KEY not found in environment variables")
                config = TTSConfig(api_key="", enabled=False)
            else:
                config = TTSConfig(api_key=api_key)

        self.config = config
        self.cache = get_audio_cache()  # Use multi-tier cache
        self.base_url = "https://api.elevenlabs.io/v1"
        self.error_handler = get_tts_error_handler()

        # Initialize connection pool for performance
        self.connection_pool = ConnectionPool(
            max_connections=10,
            connection_timeout=10.0,
            read_timeout=30.0,
            total_timeout=45.0,
        )

        # Initialize memory monitor
        self.memory_monitor = MemoryMonitor(max_memory_mb=100, cleanup_threshold=0.8)

        # Performance tracking
        self._performance_stats = {
            "requests_made": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "synthesis_times": [],
            "memory_cleanups": 0,
            "connection_reuses": 0,
        }
        self._stats_lock = threading.Lock()

        if not self.config.api_key:
            logger.warning(
                "TTS service initialized without API key - functionality disabled"
            )
            self.config.enabled = False
        else:
            logger.info(
                "TTS service initialized with connection pooling and memory management"
            )

    def is_enabled(self) -> bool:
        """Check if TTS service is enabled and not in error state."""
        return (
            self.config.enabled
            and bool(self.config.api_key)
            and not self.error_handler.is_in_error_state()
        )

    def get_error_state(self) -> Dict[str, Any]:
        """Get current error state information including circuit breaker state."""
        error_state = self.error_handler.get_error_state()
        circuit_state = self.error_handler.get_circuit_breaker_state()

        return {
            "has_error": error_state.has_error,
            "error_type": error_state.error_type,
            "error_message": error_state.error_message,
            "is_muted": error_state.is_muted,
            "consecutive_failures": error_state.consecutive_failures,
            "last_error_time": (
                error_state.last_error_time.isoformat()
                if error_state.last_error_time
                else None
            ),
            "recovery_check_count": error_state.recovery_check_count,
            "circuit_breaker": circuit_state,
        }

    async def attempt_recovery(self, test_text: str = "Hi") -> bool:
        """
        Attempt to recover from error state.

        Args:
            test_text: Text to use for health check (default: "Hi" for minimal token usage)

        Returns:
            True if recovery successful, False otherwise
        """
        return await self.error_handler.attempt_recovery(self, test_text)

    def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker to closed state."""
        self.error_handler.circuit_breaker.reset()
        logger.info("Circuit breaker manually reset")

    def set_volume(self, volume: float) -> None:
        """
        Set the volume level for TTS synthesis.

        Args:
            volume: Volume level (0.0 to 1.0)

        Raises:
            ValueError: If volume is outside valid range
        """
        if not 0.0 <= volume <= 1.0:
            raise ValueError(f"Volume must be between 0.0 and 1.0, got {volume}")
        self.config.volume = volume
        logger.info(f"TTS volume set to {volume}")

    def get_volume(self) -> float:
        """Get current volume level."""
        return self.config.volume

    def _generate_text_hash(self, text: str) -> str:
        """Generate SHA-256 hash for text content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get_cached_audio(self, text: str) -> Optional[bytes]:
        """Get cached audio for text using multi-tier cache."""
        return self.cache.get(text)

    def cache_audio(self, text: str, audio_data: bytes) -> str:
        """Cache audio data for text using multi-tier cache."""
        return self.cache.put(text, audio_data)

    async def _synthesize_with_api(
        self, text: str, voice_id: str, volume: Optional[float] = None
    ) -> bytes:
        """
        Internal method to synthesize text using ElevenLabs API with connection pooling.

        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID
            volume: Optional volume level (0.0 to 1.0), uses config default if not provided

        Returns:
            Audio data as bytes
        """
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.config.api_key,
        }

        # Use provided volume or default from config
        effective_volume = volume if volume is not None else self.config.volume

        payload = {
            "text": text,
            "model_id": self.config.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5,
                "volume": effective_volume,
            },
        }

        try:
            # Use connection pool for better performance
            session = await self.connection_pool.get_session()

            # Track performance metrics
            with self._stats_lock:
                self._performance_stats["requests_made"] += 1

            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    audio_data = await response.read()

                    # Track connection reuse
                    with self._stats_lock:
                        self._performance_stats["connection_reuses"] += 1

                    return audio_data
                elif response.status == 401:
                    error_text = await response.text()
                    raise TTSAPIKeyError(f"Invalid API key: {error_text}")
                elif response.status == 429:
                    error_text = await response.text()
                    raise TTSRateLimitError(f"Rate limit exceeded: {error_text}")
                elif 500 <= response.status < 600:
                    error_text = await response.text()
                    raise TTSServerError(f"Server error: {error_text}", response.status)
                else:
                    error_text = await response.text()
                    raise TTSError(
                        f"API request failed with status {response.status}: {error_text}"
                    )

        except asyncio.TimeoutError as e:
            raise TTSNetworkError(f"Request timeout: {str(e)}", e)
        except aiohttp.ClientConnectorError as e:
            raise TTSNetworkError(f"Connection error: {str(e)}", e)
        except aiohttp.ClientError as e:
            raise TTSNetworkError(f"Network error: {str(e)}", e)

    async def synthesize_text(
        self, text: str, voice_id: Optional[str] = None, volume: Optional[float] = None
    ) -> bytes:
        """
        Synthesize text to speech using ElevenLabs API with performance optimizations.

        Args:
            text: Text to synthesize
            voice_id: Optional voice ID (uses default if not provided)
            volume: Optional volume level (0.0 to 1.0), uses config default if not provided

        Returns:
            Audio data as bytes (volume applied)

        Raises:
            TTSError: If synthesis fails after all retries
            TTSAPIKeyError: If API key is invalid
            TTSRetryExhaustedError: If all retry attempts are exhausted
        """
        synthesis_start = time.time()

        # Check if service is enabled (includes error state check)
        if not self.config.enabled or not self.config.api_key:
            logger.warning(
                "TTS synthesis attempted but service is disabled or API key is missing"
            )
            raise TTSAPIKeyError("TTS service is not enabled or API key is missing")

        # Log synthesis request details
        logger.info(
            f"TTS synthesis request: {len(text)} characters, voice: {voice_id or self.config.voice_id}"
        )

        # Check memory usage and cleanup if needed
        if self.memory_monitor.should_cleanup():
            cleanup_results = self.memory_monitor.cleanup_memory(self.cache)
            with self._stats_lock:
                self._performance_stats["memory_cleanups"] += 1
            logger.debug(f"Memory cleanup performed: {cleanup_results}")

        # If in error state, attempt recovery
        if self.error_handler.is_in_error_state():
            logger.info("TTS service in error state, attempting recovery...")
            recovery_attempted = await self.error_handler.attempt_recovery(self)
            if not recovery_attempted or self.error_handler.is_in_error_state():
                error_state = self.error_handler.get_error_state()
                logger.error(f"TTS recovery failed: {error_state.error_message}")
                raise TTSError(
                    f"TTS service is in error state: {error_state.error_message}",
                    error_code=error_state.error_type,
                )
            else:
                logger.info("TTS service recovery successful")

        if not text.strip():
            logger.warning("TTS synthesis failed: empty text provided")
            raise TTSError("Empty text provided for synthesis")

        # Check cache first
        cached_audio = self.get_cached_audio(text)
        if cached_audio:
            with self._stats_lock:
                self._performance_stats["cache_hits"] += 1
            logger.info(
                f"TTS cache hit: returning {len(cached_audio)} bytes of cached audio"
            )
            return cached_audio

        # Cache miss - track it
        with self._stats_lock:
            self._performance_stats["cache_misses"] += 1
        logger.debug("TTS cache miss, proceeding with API synthesis")

        # Use provided voice_id or default
        voice_id = voice_id or self.config.voice_id

        # Validate only when caller supplied an explicit volume
        if volume is not None:
            validate_volume_strict(volume)
        try:
            # Use error handler for retry logic, passing volume directly to API method
            audio_data = await self.error_handler.execute_with_retry(
                self._synthesize_with_api, text, voice_id, volume
            )

            # Cache the audio
            cache_key = self.cache_audio(text, audio_data)

            # Track synthesis performance
            synthesis_time = time.time() - synthesis_start
            with self._stats_lock:
                self._performance_stats["synthesis_times"].append(synthesis_time)
                # Keep only last 100 synthesis times for memory efficiency
                if len(self._performance_stats["synthesis_times"]) > 100:
                    self._performance_stats["synthesis_times"] = (
                        self._performance_stats["synthesis_times"][-100:]
                    )

            logger.info(
                f"Successfully synthesized {len(audio_data)} bytes of audio in {synthesis_time:.2f}s (cached as {cache_key[:8]}...)"
            )
            return audio_data

        except (TTSAPIKeyError, TTSRetryExhaustedError):
            # These are already properly handled by the error handler
            raise
        except Exception as e:
            # Wrap unexpected errors
            logger.error(f"Unexpected error during TTS synthesis: {e}")
            raise TTSError(f"Synthesis failed: {e}", original_error=e)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics from all tiers."""
        return self.cache.get_comprehensive_stats()

    def clear_cache(self) -> None:
        """Clear all cache tiers."""
        self.cache.clear()

    def warm_cache(self, entries: list[tuple[str, bytes]]) -> int:
        """Warm cache with frequently accessed entries."""
        return self.cache.warm_cache(entries)

    def cleanup_expired_cache(self) -> Dict[str, int]:
        """Clean up expired entries from all cache tiers."""
        return self.cache.cleanup_expired()

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        with self._stats_lock:
            synthesis_times = self._performance_stats["synthesis_times"].copy()

            # Calculate synthesis time statistics
            synthesis_stats = {}
            if synthesis_times:
                synthesis_stats = {
                    "avg_synthesis_time": sum(synthesis_times) / len(synthesis_times),
                    "min_synthesis_time": min(synthesis_times),
                    "max_synthesis_time": max(synthesis_times),
                    "total_syntheses": len(synthesis_times),
                }

            # Get connection pool stats
            connection_stats = self.connection_pool.get_stats()

            # Get memory usage stats
            memory_stats = self.memory_monitor.get_memory_usage()

            # Calculate cache hit rate
            total_requests = (
                self._performance_stats["cache_hits"]
                + self._performance_stats["cache_misses"]
            )
            cache_hit_rate = self._performance_stats["cache_hits"] / max(
                total_requests, 1
            )

            return {
                "requests": {
                    "total_requests": self._performance_stats["requests_made"],
                    "cache_hits": self._performance_stats["cache_hits"],
                    "cache_misses": self._performance_stats["cache_misses"],
                    "cache_hit_rate": cache_hit_rate,
                    "connection_reuses": self._performance_stats["connection_reuses"],
                },
                "synthesis": synthesis_stats,
                "memory": {
                    **memory_stats,
                    "cleanup_count": self._performance_stats["memory_cleanups"],
                },
                "connections": connection_stats,
                "cache": self.get_cache_stats(),
            }

    def optimize_performance(self) -> Dict[str, Any]:
        """Perform performance optimization operations."""
        optimization_results = {
            "cache_cleanup": {},
            "memory_cleanup": {},
            "connection_cleanup": False,
        }

        try:
            # Clean up expired cache entries
            optimization_results["cache_cleanup"] = self.cleanup_expired_cache()

            # Perform memory cleanup
            optimization_results["memory_cleanup"] = self.memory_monitor.cleanup_memory(
                self.cache
            )

            # Clean up connection pool
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.connection_pool._cleanup_connections())
                else:
                    loop.run_until_complete(self.connection_pool._cleanup_connections())
            except RuntimeError:
                # No event loop available
                logger.warning("Could not perform connection cleanup - no event loop")

            optimization_results["connection_cleanup"] = True
            logger.info(f"Performance optimization completed: {optimization_results}")

        except Exception as e:
            logger.error(f"Performance optimization failed: {e}")
            optimization_results["error"] = str(e)

        return optimization_results

    async def cleanup_resources(self):
        """Clean up TTS service resources."""
        try:
            # Clean up connection pool
            await self.connection_pool.cleanup()

            # Clear cache
            self.cache.clear()

            # Reset performance stats
            with self._stats_lock:
                self._performance_stats = {
                    "requests_made": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "synthesis_times": [],
                    "memory_cleanups": 0,
                    "connection_reuses": 0,
                }

            logger.info("TTS service resources cleaned up successfully")

        except Exception as e:
            logger.error(f"Resource cleanup failed: {e}")

    def __del__(self):
        """Log warning if resources weren't cleaned up properly."""
        if (
            hasattr(self, "connection_pool")
            and self.connection_pool._session
            and not self.connection_pool._session.closed
        ):
            logger.warning(
                "TTSService deleted without proper cleanup. Call cleanup_resources() explicitly."
            )


# Global TTS service instance
_tts_service: Optional[TTSService] = None


# Global TTS service instance
_tts_service: Optional[TTSService] = None
_lock = threading.Lock()


def get_tts_service() -> TTSService:
    """Get global TTS service instance."""
    global _tts_service
    if _tts_service is None:
        with _lock:
            if _tts_service is None:
                _tts_service = TTSService()
    return _tts_service


def initialize_tts_service(config: Optional[TTSConfig] = None) -> TTSService:
    """Initialize global TTS service with custom configuration."""
    global _tts_service
    with _lock:
        # Clean up existing service if present
        if _tts_service:
            try:
                # Running async cleanup in a sync function
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(_tts_service.cleanup_resources())
                else:
                    loop.run_until_complete(_tts_service.cleanup_resources())
            except Exception as e:
                logger.warning(f"Error cleaning up existing TTS service: {e}")

        _tts_service = TTSService(config)
    return _tts_service


async def cleanup_tts_service():
    """Clean up global TTS service resources."""
    global _tts_service
    if _tts_service:
        try:
            await _tts_service.cleanup_resources()
        except Exception as e:
            logger.warning(f"Error during TTS service cleanup: {e}")
        finally:
            _tts_service = None


def _sync_cleanup_tts_service():
    """Synchronous wrapper for async cleanup function to work with atexit."""
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we can't use run_until_complete
            # Create a new task instead (best effort cleanup)
            asyncio.create_task(cleanup_tts_service())
        else:
            # Loop exists but not running, we can use it
            loop.run_until_complete(cleanup_tts_service())
    except RuntimeError:
        # No event loop exists, create a new one
        try:
            asyncio.run(cleanup_tts_service())
        except Exception as e:
            logger.warning(f"Failed to run async cleanup during exit: {e}")
    except Exception as e:
        logger.warning(f"Error during synchronous TTS service cleanup: {e}")


# Register cleanup on module exit
import atexit  # noqa: E402

atexit.register(_sync_cleanup_tts_service)
