"""
Text-to-Speech service using ElevenLabs API with multi-tier caching and error handling.
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


class TTSError(Exception):
    """Custom exception for TTS-related errors."""
    pass


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
    """Text-to-Speech service with ElevenLabs integration and multi-tier caching."""
    
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
        
        # Retry configuration for rate limiting and errors
        self.retry_config = {
            'max_retries_429': 3,
            'max_retries_5xx': 2,
            'base_delay_429': 1.0,
            'base_delay_5xx': 0.5,
            'max_delay_429': 16.0,
            'max_delay_5xx': 8.0,
            'jitter_factor': 0.25
        }
        
        if not self.config.api_key:
            logger.warning("TTS service initialized without API key - functionality disabled")
            self.config.enabled = False
        else:
            logger.info("TTS service initialized successfully with multi-tier caching")
    
    def is_enabled(self) -> bool:
        """Check if TTS service is enabled."""
        return self.config.enabled and bool(self.config.api_key)

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
    
    def _calculate_backoff_delay(self, attempt: int, base_delay: float, max_delay: float) -> float:
        """Calculate exponential backoff delay with jitter."""
        import random
        
        # Exponential backoff: base_delay * (2 ^ attempt)
        delay = base_delay * (2 ** attempt)
        delay = min(delay, max_delay)
        
        # Add jitter (±25% of calculated delay)
        jitter = delay * self.retry_config['jitter_factor']
        delay += random.uniform(-jitter, jitter)
        
        return max(0, delay)
    
    async def synthesize_text(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """
        Synthesize text to speech using ElevenLabs API with retry logic.

        Args:
            text: Text to synthesize
            voice_id: Optional voice ID (uses default if not provided)

        Returns:
            Audio data as bytes (volume applied from config)

        Raises:
            TTSError: If synthesis fails after all retries
        """
        if not self.is_enabled():
            raise TTSError("TTS service is not enabled or API key is missing")
        
        if not text.strip():
            raise TTSError("Empty text provided for synthesis")
        
        # Check cache first
        cached_audio = self.get_cached_audio(text)
        if cached_audio:
            logger.debug("Using cached audio for synthesis")
            return cached_audio
        
        # Use provided voice_id or default
        voice_id = voice_id or self.config.voice_id
        
        # Prepare API request
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.config.api_key
        }
        
        payload = {
            "text": text,
            "model_id": self.config.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5,
                "volume": self.config.volume
            }
        }
        
        last_error = None
        
        # Retry logic with exponential backoff
        for attempt in range(max(self.retry_config['max_retries_429'], self.retry_config['max_retries_5xx']) + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            audio_data = await response.read()
                            
                            # Cache the audio
                            cache_key = self.cache_audio(text, audio_data)
                            
                            logger.info(f"Successfully synthesized {len(audio_data)} bytes of audio (cached as {cache_key[:8]}...)")
                            return audio_data
                        
                        elif response.status == 429:  # Rate limit
                            if attempt < self.retry_config['max_retries_429']:
                                delay = self._calculate_backoff_delay(
                                    attempt, 
                                    self.retry_config['base_delay_429'],
                                    self.retry_config['max_delay_429']
                                )
                                error_text = await response.text()
                                logger.warning(f"Rate limited (429), retrying in {delay:.2f}s (attempt {attempt + 1}/{self.retry_config['max_retries_429'] + 1}): {error_text}")
                                await asyncio.sleep(delay)
                                continue
                            else:
                                error_text = await response.text()
                                last_error = TTSError(f"Rate limit exceeded after {self.retry_config['max_retries_429']} retries: {error_text}")
                                break
                        
                        elif 500 <= response.status < 600:  # Server errors
                            if attempt < self.retry_config['max_retries_5xx']:
                                delay = self._calculate_backoff_delay(
                                    attempt,
                                    self.retry_config['base_delay_5xx'],
                                    self.retry_config['max_delay_5xx']
                                )
                                error_text = await response.text()
                                logger.warning(f"Server error ({response.status}), retrying in {delay:.2f}s (attempt {attempt + 1}/{self.retry_config['max_retries_5xx'] + 1}): {error_text}")
                                await asyncio.sleep(delay)
                                continue
                            else:
                                error_text = await response.text()
                                last_error = TTSError(f"Server error after {self.retry_config['max_retries_5xx']} retries: {error_text}")
                                break
                        
                        else:
                            # Other HTTP errors (4xx except 429) - don't retry
                            error_text = await response.text()
                            last_error = TTSError(f"API request failed with status {response.status}: {error_text}")
                            break
            
            except aiohttp.ClientError as e:
                logger.error(f"Network error during TTS synthesis (attempt {attempt + 1}): {e}")
                last_error = TTSError(f"Network error: {e}")
                if attempt < self.retry_config['max_retries_5xx']:
                    delay = self._calculate_backoff_delay(
                        attempt,
                        self.retry_config['base_delay_5xx'],
                        self.retry_config['max_delay_5xx']
                    )
                    logger.warning(f"Retrying network request in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    break
            
            except Exception as e:
                logger.error(f"Unexpected error during TTS synthesis: {e}")
                last_error = TTSError(f"Synthesis failed: {e}")
                break
        
        # If we get here, all retries failed
        if last_error:
            raise last_error
        else:
            raise TTSError("Synthesis failed after all retry attempts")
    
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