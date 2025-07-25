"""
Text-to-Speech service using ElevenLabs API with multi-tier caching and comprehensive error handling.
"""

import os
import hashlib
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from collections import OrderedDict
import asyncio
import aiohttp

from .multi_tier_audio_cache import get_audio_cache, MultiTierAudioCache, CacheConfig
from .tts_error_handler import (
    TTSError, TTSAPIKeyError, TTSRateLimitError, TTSServerError, 
    TTSNetworkError, TTSRetryExhaustedError, get_tts_error_handler
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
            size_bytes=size_bytes
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
        
        logger.debug(f"Cached audio for text hash: {text_hash[:8]}... (size: {size_bytes} bytes)")
    
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
            "max_size": self.max_size
        }


class TTSService:
    """Text-to-Speech service with ElevenLabs integration, multi-tier caching, and comprehensive error handling."""
    
    def __init__(self, config: Optional[TTSConfig] = None, cache_config: Optional[CacheConfig] = None):
        """Initialize TTS service."""
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
        
        if not self.config.api_key:
            logger.warning("TTS service initialized without API key - functionality disabled")
            self.config.enabled = False
        else:
            logger.info("TTS service initialized successfully with multi-tier caching and error handling")
    
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
            "last_error_time": error_state.last_error_time.isoformat() if error_state.last_error_time else None,
            "recovery_check_count": error_state.recovery_check_count,
            "circuit_breaker": circuit_state
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
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def get_cached_audio(self, text: str) -> Optional[bytes]:
        """Get cached audio for text using multi-tier cache."""
        return self.cache.get(text)
    
    def cache_audio(self, text: str, audio_data: bytes) -> str:
        """Cache audio data for text using multi-tier cache."""
        return self.cache.put(text, audio_data)
    
    async def _synthesize_with_api(self, text: str, voice_id: str, volume: Optional[float] = None) -> bytes:
        """
        Internal method to synthesize text using ElevenLabs API with timeout handling.
        
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
            "xi-api-key": self.config.api_key
        }
        
        # Use provided volume or default from config
        effective_volume = volume if volume is not None else self.config.volume
        
        payload = {
            "text": text,
            "model_id": self.config.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5,
                "volume": effective_volume
            }
        }
        
        # Configure timeouts from error handler
        timeout_config = self.error_handler.retry_config
        timeout = aiohttp.ClientTimeout(
            connect=timeout_config['connection_timeout'],
            sock_read=timeout_config['read_timeout'],
            total=timeout_config['total_timeout']
        )
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()
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
                        raise TTSError(f"API request failed with status {response.status}: {error_text}")
        
        except asyncio.TimeoutError as e:
            raise TTSNetworkError(f"Request timeout: {str(e)}", e)
        except aiohttp.ClientConnectorError as e:
            raise TTSNetworkError(f"Connection error: {str(e)}", e)
        except aiohttp.ClientError as e:
            raise TTSNetworkError(f"Network error: {str(e)}", e)
    
    async def synthesize_text(self, text: str, voice_id: Optional[str] = None, volume: Optional[float] = None) -> bytes:
        """
        Synthesize text to speech using ElevenLabs API with comprehensive error handling.

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
        # Check if service is enabled (includes error state check)
        if not self.config.enabled or not self.config.api_key:
            raise TTSAPIKeyError("TTS service is not enabled or API key is missing")
        
        # If in error state, attempt recovery
        if self.error_handler.is_in_error_state():
            recovery_attempted = await self.error_handler.attempt_recovery(self)
            if not recovery_attempted or self.error_handler.is_in_error_state():
                error_state = self.error_handler.get_error_state()
                raise TTSError(
                    f"TTS service is in error state: {error_state.error_message}",
                    error_code=error_state.error_type
                )
        
        if not text.strip():
            raise TTSError("Empty text provided for synthesis")
        
        # Check cache first
        cached_audio = self.get_cached_audio(text)
        if cached_audio:
            logger.debug("Using cached audio for synthesis")
            return cached_audio
        
        # Use provided voice_id or default
        voice_id = voice_id or self.config.voice_id
        
        # Validate volume parameter if provided
        if volume is not None and not 0.0 <= volume <= 1.0:
            raise ValueError(f"Volume must be between 0.0 and 1.0, got {volume}")
        
        try:
            # Use error handler for retry logic, passing volume directly to API method
            audio_data = await self.error_handler.execute_with_retry(
                self._synthesize_with_api, text, voice_id, volume
            )
            
            # Cache the audio
            cache_key = self.cache_audio(text, audio_data)
            
            logger.info(f"Successfully synthesized {len(audio_data)} bytes of audio (cached as {cache_key[:8]}...)")
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


# Global TTS service instance
_tts_service: Optional[TTSService] = None


import threading

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
        _tts_service = TTSService(config)
    return _tts_service