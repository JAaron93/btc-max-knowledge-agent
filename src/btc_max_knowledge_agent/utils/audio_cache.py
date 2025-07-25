"""
Audio caching system for TTS responses.

This module provides an in-memory cache for storing generated audio data
with LRU eviction policy and SHA-256 hash-based keys.
"""

import hashlib
import time
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached audio entry with metadata."""
    text_hash: str
    audio_data: bytes
    timestamp: datetime
    access_count: int
    size_bytes: Optional[int] = None

    def __post_init__(self):
        """Calculate size if not provided."""
        if self.size_bytes is None:
            self.size_bytes = len(self.audio_data)


class AudioCache:
    """
    Thread-safe in-memory LRU cache for storing generated audio data.

    Uses SHA-256 hashes of response text as cache keys and implements
    LRU eviction policy with configurable size limits.
    """

    def __init__(self, max_size: int = 100, max_memory_mb: int = 50):
        """
        Initialize the audio cache.

        Args:
            max_size: Maximum number of entries to store
            max_memory_mb: Maximum memory usage in megabytes
        """
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._total_size_bytes = 0
        self._lock = threading.Lock()

        logger.info(f"AudioCache initialized with max_size={max_size}, max_memory_mb={max_memory_mb}")
    
    def _generate_hash(self, text: str) -> str:
        """
        Generate SHA-256 hash for the given text.
        
        Args:
            text: Text to hash
            
        Returns:
            SHA-256 hash as hexadecimal string
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _evict_if_needed(self) -> None:
        """Evict entries if cache exceeds size or memory limits."""
        # Evict by count limit
        while len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        # Evict by memory limit
        while self._total_size_bytes > self.max_memory_bytes and self._cache:
            self._evict_oldest()
    
    def _evict_oldest(self) -> None:
        """Remove the least recently used entry."""
        if not self._cache:
            return
            
        oldest_key, oldest_entry = self._cache.popitem(last=False)
        self._total_size_bytes -= oldest_entry.size_bytes
        
        logger.debug(f"Evicted cache entry: {oldest_key[:8]}... (size: {oldest_entry.size_bytes} bytes)")
    
    def put(self, text: str, audio_data: bytes) -> str:
        """
        Store audio data in cache (thread-safe).

        Args:
            text: Original text that was synthesized
            audio_data: Generated audio data

        Returns:
            Cache key (hash) for the stored entry
        """
        text_hash = self._generate_hash(text)

        with self._lock:
            # If entry already exists, update it and move to end (most recent)
            if text_hash in self._cache:
                old_entry = self._cache.pop(text_hash)
                self._total_size_bytes -= old_entry.size_bytes

            # Create new entry
            entry = CacheEntry(
                text_hash=text_hash,
                audio_data=audio_data,
                timestamp=datetime.now(timezone.utc),
                access_count=0
                # size_bytes will be calculated automatically in __post_init__
            )

            # Check if we need to evict entries to make room for the new entry
            # Temporarily add the new entry size to check if we exceed limits
            temp_total_size = self._total_size_bytes + entry.size_bytes

            # Evict by count limit (considering the new entry)
            while len(self._cache) >= self.max_size:
                self._evict_oldest()

            # Evict by memory limit (considering the new entry)
            while temp_total_size > self.max_memory_bytes and self._cache:
                self._evict_oldest()
                temp_total_size = self._total_size_bytes + entry.size_bytes

            # Add new entry
            self._cache[text_hash] = entry
            self._total_size_bytes += entry.size_bytes

            logger.debug(f"Cached audio: {text_hash[:8]}... (size: {entry.size_bytes} bytes)")

            return text_hash
    
    def get(self, text: str) -> Optional[bytes]:
        """
        Retrieve audio data from cache.
        
        Args:
            text: Original text to look up
            
        Returns:
            Audio data if found, None otherwise
        """
        text_hash = self._generate_hash(text)
        return self.get_by_hash(text_hash)
    
    def get_by_hash(self, text_hash: str) -> Optional[bytes]:
        """
        Retrieve audio data from cache by hash (thread-safe).

        Args:
            text_hash: SHA-256 hash of the original text

        Returns:
            Audio data if found, None otherwise
        """
        with self._lock:
            if text_hash not in self._cache:
                logger.debug(f"Cache miss: {text_hash[:8]}...")
                return None

            # Move to end (most recent) and update access count
            entry = self._cache.pop(text_hash)
            entry.access_count += 1
            self._cache[text_hash] = entry

            logger.debug(f"Cache hit: {text_hash[:8]}... (access_count: {entry.access_count})")

            return entry.audio_data
    
    def has(self, text: str) -> bool:
        """
        Check if text is cached.
        
        Args:
            text: Text to check
            
        Returns:
            True if cached, False otherwise
        """
        text_hash = self._generate_hash(text)
        return text_hash in self._cache
    
    def has_hash(self, text_hash: str) -> bool:
        """
        Check if hash is cached (thread-safe).

        Args:
            text_hash: Hash to check

        Returns:
            True if cached, False otherwise
        """
        with self._lock:
            return text_hash in self._cache
    
    def remove(self, text: str) -> bool:
        """
        Remove entry from cache.
        
        Args:
            text: Text whose entry to remove
            
        Returns:
            True if removed, False if not found
        """
        text_hash = self._generate_hash(text)
        return self.remove_by_hash(text_hash)
    
    def remove_by_hash(self, text_hash: str) -> bool:
        """
        Remove entry from cache by hash (thread-safe).

        Args:
            text_hash: Hash of entry to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if text_hash not in self._cache:
                return False

            entry = self._cache.pop(text_hash)
            self._total_size_bytes -= entry.size_bytes

            logger.debug(f"Removed cache entry: {text_hash[:8]}...")

            return True
    
    def clear(self) -> None:
        """Clear all cached entries (thread-safe)."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._total_size_bytes = 0

            logger.info(f"Cleared {count} cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics (thread-safe).

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                'entry_count': len(self._cache),
                'max_size': self.max_size,
                'total_size_bytes': self._total_size_bytes,
                'max_memory_bytes': self.max_memory_bytes,
                'memory_usage_percent': (self._total_size_bytes / self.max_memory_bytes) * 100 if self.max_memory_bytes > 0 else 0,
                'entries': [
                    {
                        'hash': entry.text_hash[:8] + '...',
                        'size_bytes': entry.size_bytes,
                        'access_count': entry.access_count,
                        'timestamp': entry.timestamp.isoformat()
                    }
                    for entry in self._cache.values()
                ]
            }
    
    def __len__(self) -> int:
        """Return number of cached entries (thread-safe)."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, text: str) -> bool:
        """Check if text is in cache (supports 'in' operator)."""
        return self.has(text)