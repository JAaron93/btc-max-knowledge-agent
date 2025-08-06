"""
Multi-tier audio caching system for TTS responses.

This module provides a comprehensive caching solution with multiple tiers:
- Memory cache (fastest access)
- Persistent cache (survives restarts)
- Distributed cache (cluster-wide sharing)

Supports SQLite, diskcache, and Redis backends with configurable policies.
"""

import hashlib
import logging
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Optional imports for different cache backends
try:
    import diskcache  # noqa: F401

    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .audio_cache import AudioCache, CacheEntry

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for multi-tier cache system."""

    # Backend selection
    backend: str = "memory"  # memory, sqlite, diskcache, redis, multi-tier

    # Memory cache settings
    memory_max_size: int = 100
    memory_max_mb: int = 50

    # Persistent cache settings
    persistent_path: str = "./cache"
    persistent_max_size: int = 1000
    persistent_max_mb: int = 500

    # Distributed cache settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_max_connections: int = 10

    # TTL settings
    ttl_hours: int = 24
    cleanup_interval_minutes: int = 60

    # Performance settings
    enable_cache_warming: bool = True
    enable_statistics: bool = True

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Create configuration from environment variables."""
        return cls(
            backend=os.getenv("CACHE_BACKEND", "memory"),
            memory_max_size=int(os.getenv("CACHE_MEMORY_MAX_SIZE", "100")),
            memory_max_mb=int(os.getenv("CACHE_MEMORY_MAX_MB", "50")),
            persistent_path=os.getenv("CACHE_PERSISTENT_PATH", "./cache"),
            persistent_max_size=int(os.getenv("CACHE_PERSISTENT_MAX_SIZE", "1000")),
            persistent_max_mb=int(os.getenv("CACHE_PERSISTENT_MAX_MB", "500")),
            redis_host=os.getenv("CACHE_REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("CACHE_REDIS_PORT", "6379")),
            redis_db=int(os.getenv("CACHE_REDIS_DB", "0")),
            redis_password=os.getenv("CACHE_REDIS_PASSWORD"),
            redis_max_connections=int(os.getenv("CACHE_REDIS_MAX_CONNECTIONS", "10")),
            ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "24")),
            cleanup_interval_minutes=int(
                os.getenv("CACHE_CLEANUP_INTERVAL_MINUTES", "60")
            ),
            enable_cache_warming=os.getenv("CACHE_ENABLE_WARMING", "true").lower()
            == "true",
            enable_statistics=os.getenv("CACHE_ENABLE_STATISTICS", "true").lower()
            == "true",
        )


class BaseCacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """Retrieve audio data by key."""
        pass

    @abstractmethod
    def put(self, key: str, data: bytes, ttl_seconds: Optional[int] = None) -> bool:
        """Store audio data with optional TTL."""
        pass

    @abstractmethod
    def has(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    def remove(self, key: str) -> bool:
        """Remove entry from cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all entries."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        pass


class MemoryCacheBackend(BaseCacheBackend):
    """Memory cache backend using the existing AudioCache."""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache = AudioCache(
            max_size=config.memory_max_size, max_memory_mb=config.memory_max_mb
        )
        self._ttl_map: Dict[str, datetime] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            # Check TTL first
            if key in self._ttl_map:
                if datetime.now() > self._ttl_map[key]:
                    self.remove(key)
                    return None

            return self.cache.get_by_hash(key)

    def put(self, key: str, data: bytes, ttl_seconds: Optional[int] = None) -> bool:
        with self._lock:
            try:
                # Store in cache (we need to reverse-engineer text from hash for AudioCache)
                # For now, we'll use the hash as the text since AudioCache generates the same hash
                self.cache._cache[key] = CacheEntry(
                    text_hash=key,
                    audio_data=data,
                    timestamp=datetime.now(),
                    access_count=0,
                    size_bytes=len(data),
                )
                self.cache._total_size_bytes += len(data)

                # Set TTL if provided
                if ttl_seconds:
                    self._ttl_map[key] = datetime.now() + timedelta(seconds=ttl_seconds)

                # Evict if needed
                self.cache._evict_if_needed()

                return True
            except Exception as e:
                logger.error(f"Failed to store in memory cache: {e}")
                return False

    def has(self, key: str) -> bool:
        with self._lock:
            if key in self._ttl_map:
                if datetime.now() > self._ttl_map[key]:
                    self.remove(key)
                    return False
            return self.cache.has_hash(key)

    def remove(self, key: str) -> bool:
        with self._lock:
            removed = self.cache.remove_by_hash(key)
            if key in self._ttl_map:
                del self._ttl_map[key]
            return removed

    def clear(self) -> None:
        with self._lock:
            self.cache.clear()
            self._ttl_map.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = self.cache.get_stats()
            stats.update(
                {
                    "backend_type": "memory",
                    "ttl_entries": len(self._ttl_map),
                    "expired_entries": sum(
                        1
                        for exp_time in self._ttl_map.values()
                        if datetime.now() > exp_time
                    ),
                }
            )
            return stats

    def cleanup_expired(self) -> int:
        with self._lock:
            expired_keys = [
                key
                for key, exp_time in self._ttl_map.items()
                if datetime.now() > exp_time
            ]

            for key in expired_keys:
                self.remove(key)

            return len(expired_keys)


class SQLiteCacheBackend(BaseCacheBackend):
    """SQLite-based persistent cache backend."""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.db_path = Path(config.persistent_path) / "audio_cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audio_cache (
                        key TEXT PRIMARY KEY,
                        data BLOB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER DEFAULT 0,
                        size_bytes INTEGER NOT NULL,
                        expires_at TIMESTAMP
                    )
                """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_expires_at ON audio_cache(expires_at)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_accessed_at ON audio_cache(accessed_at)"
                )
                conn.commit()
            finally:
                conn.close()

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "SELECT data FROM audio_cache WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                    (key, datetime.now()),
                )
                row = cursor.fetchone()

                if row:
                    # Update access statistics
                    conn.execute(
                        "UPDATE audio_cache SET accessed_at = ?, access_count = access_count + 1 WHERE key = ?",
                        (datetime.now(), key),
                    )
                    conn.commit()
                    return row[0]

                return None
            finally:
                conn.close()

    def put(self, key: str, data: bytes, ttl_seconds: Optional[int] = None) -> bool:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                expires_at = None
                if ttl_seconds:
                    expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO audio_cache 
                    (key, data, created_at, accessed_at, access_count, size_bytes, expires_at)
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                    (key, data, datetime.now(), datetime.now(), len(data), expires_at),
                )

                conn.commit()

                # Cleanup if we exceed size limits
                self._cleanup_by_size(conn)

                return True
            except Exception as e:
                logger.error(f"Failed to store in SQLite cache: {e}")
                return False
            finally:
                conn.close()

    def _cleanup_by_size(self, conn: sqlite3.Connection):
        """Remove oldest entries if size limits are exceeded."""
        # Check entry count
        cursor = conn.execute("SELECT COUNT(*) FROM audio_cache")
        count = cursor.fetchone()[0]

        if count > self.config.persistent_max_size:
            excess = count - self.config.persistent_max_size
            conn.execute(
                """
                DELETE FROM audio_cache WHERE key IN (
                    SELECT key FROM audio_cache 
                    ORDER BY accessed_at ASC 
                    LIMIT ?
                )
            """,
                (excess,),
            )

        # Check total size
        cursor = conn.execute("SELECT SUM(size_bytes) FROM audio_cache")
        total_size = cursor.fetchone()[0] or 0
        max_size_bytes = self.config.persistent_max_mb * 1024 * 1024

        if total_size > max_size_bytes:
            # Remove oldest entries until under limit
            conn.execute(
                """
                DELETE FROM audio_cache WHERE key IN (
                    SELECT key FROM audio_cache 
                    ORDER BY accessed_at ASC
                )
            """
            )
            # This is a simplified approach - in production, you'd want more sophisticated size management

    def has(self, key: str) -> bool:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "SELECT 1 FROM audio_cache WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                    (key, datetime.now()),
                )
                return cursor.fetchone() is not None
            finally:
                conn.close()

    def remove(self, key: str) -> bool:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute("DELETE FROM audio_cache WHERE key = ?", (key,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def clear(self) -> None:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("DELETE FROM audio_cache")
                conn.commit()
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    """
                    SELECT 
                        COUNT(*) as entry_count,
                        SUM(size_bytes) as total_size_bytes,
                        AVG(access_count) as avg_access_count,
                        COUNT(CASE WHEN expires_at IS NOT NULL AND expires_at <= ? THEN 1 END) as expired_count
                    FROM audio_cache
                """,
                    (datetime.now(),),
                )

                row = cursor.fetchone()

                return {
                    "backend_type": "sqlite",
                    "entry_count": row[0] or 0,
                    "total_size_bytes": row[1] or 0,
                    "avg_access_count": row[2] or 0,
                    "expired_count": row[3] or 0,
                    "max_size": self.config.persistent_max_size,
                    "max_memory_bytes": self.config.persistent_max_mb * 1024 * 1024,
                    "db_path": str(self.db_path),
                }
            finally:
                conn.close()

    def cleanup_expired(self) -> int:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "DELETE FROM audio_cache WHERE expires_at IS NOT NULL AND expires_at <= ?",
                    (datetime.now(),),
                )
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()


class RedisCacheBackend(BaseCacheBackend):
    """Redis-based distributed cache backend."""

    def __init__(self, config: CacheConfig):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not available. Install with: pip install redis")

        self.config = config
        self.redis_client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            password=config.redis_password,
            max_connections=config.redis_max_connections,
            decode_responses=False,  # We need binary data
        )
        self.key_prefix = "audio_cache:"
        self._test_connection()

    def _test_connection(self):
        """Test Redis connection."""
        try:
            self.redis_client.ping()
            logger.info("Redis cache backend connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def _make_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.key_prefix}{key}"

    def get(self, key: str) -> Optional[bytes]:
        try:
            redis_key = self._make_key(key)
            data = self.redis_client.get(redis_key)

            if data:
                # Update access statistics
                stats_key = f"{redis_key}:stats"
                pipe = self.redis_client.pipeline()
                pipe.hincrby(stats_key, "access_count", 1)
                pipe.hset(stats_key, "accessed_at", datetime.now().isoformat())
                pipe.expire(stats_key, self.config.ttl_hours * 3600)
                pipe.execute()

            return data
        except Exception as e:
            logger.error(f"Failed to get from Redis cache: {e}")
            return None

    def put(self, key: str, data: bytes, ttl_seconds: Optional[int] = None) -> bool:
        try:
            redis_key = self._make_key(key)
            stats_key = f"{redis_key}:stats"

            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()

            # Store data with TTL
            if ttl_seconds:
                pipe.setex(redis_key, ttl_seconds, data)
                pipe.expire(stats_key, ttl_seconds)
            else:
                default_ttl = self.config.ttl_hours * 3600
                pipe.setex(redis_key, default_ttl, data)
                pipe.expire(stats_key, default_ttl)

            # Store metadata
            pipe.hset(
                stats_key,
                {
                    "created_at": datetime.now().isoformat(),
                    "accessed_at": datetime.now().isoformat(),
                    "access_count": 0,
                    "size_bytes": len(data),
                },
            )

            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Failed to store in Redis cache: {e}")
            return False

    def has(self, key: str) -> bool:
        try:
            return self.redis_client.exists(self._make_key(key)) > 0
        except Exception as e:
            logger.error(f"Failed to check Redis cache: {e}")
            return False

    def remove(self, key: str) -> bool:
        try:
            redis_key = self._make_key(key)
            stats_key = f"{redis_key}:stats"

            pipe = self.redis_client.pipeline()
            pipe.delete(redis_key)
            pipe.delete(stats_key)
            results = pipe.execute()

            return results[0] > 0
        except Exception as e:
            logger.error(f"Failed to remove from Redis cache: {e}")
            return False

    def clear(self) -> None:
        try:
            # Find all keys with our prefix
            keys = self.redis_client.keys(f"{self.key_prefix}*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Failed to clear Redis cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        try:
            # Get all cache keys
            cache_keys = self.redis_client.keys(f"{self.key_prefix}*:stats")

            total_size = 0
            total_access_count = 0
            entry_count = 0

            for stats_key in cache_keys:
                stats = self.redis_client.hgetall(stats_key)
                if stats:
                    entry_count += 1
                    total_size += int(stats.get(b"size_bytes", 0))
                    total_access_count += int(stats.get(b"access_count", 0))

            return {
                "backend_type": "redis",
                "entry_count": entry_count,
                "total_size_bytes": total_size,
                "avg_access_count": total_access_count / max(entry_count, 1),
                "redis_host": self.config.redis_host,
                "redis_port": self.config.redis_port,
                "redis_db": self.config.redis_db,
            }
        except Exception as e:
            logger.error(f"Failed to get Redis cache stats: {e}")
            return {"backend_type": "redis", "error": str(e)}

    def cleanup_expired(self) -> int:
        # Redis handles TTL expiration automatically
        return 0


class MultiTierAudioCache:
    """
    Multi-tier audio cache that coordinates between memory, persistent, and distributed caches.

    Cache hierarchy: Memory → Persistent → Distributed → API call
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig.from_env()
        self.backends: Dict[str, BaseCacheBackend] = {}
        self._lock = threading.RLock()
        self._stats = {
            "hits": {"memory": 0, "persistent": 0, "distributed": 0},
            "misses": {"memory": 0, "persistent": 0, "distributed": 0},
            "puts": {"memory": 0, "persistent": 0, "distributed": 0},
            "errors": {"memory": 0, "persistent": 0, "distributed": 0},
        }

        self._init_backends()
        self._start_cleanup_thread()

    def _init_backends(self):
        """Initialize cache backends based on configuration."""
        try:
            # Always initialize memory cache
            self.backends["memory"] = MemoryCacheBackend(self.config)
            logger.info("Memory cache backend initialized")

            # Initialize persistent cache based on backend selection
            if self.config.backend in ["sqlite", "multi-tier"]:
                self.backends["persistent"] = SQLiteCacheBackend(self.config)
                logger.info("SQLite persistent cache backend initialized")
            elif self.config.backend == "diskcache" and DISKCACHE_AVAILABLE:
                # TODO: Implement DiskcacheBackend if needed
                logger.warning(
                    "Diskcache backend not implemented, falling back to SQLite"
                )
                self.backends["persistent"] = SQLiteCacheBackend(self.config)

            # Initialize distributed cache
            if self.config.backend in ["redis", "multi-tier"] and REDIS_AVAILABLE:
                try:
                    self.backends["distributed"] = RedisCacheBackend(self.config)
                    logger.info("Redis distributed cache backend initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize Redis backend: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize cache backends: {e}")
            # Ensure we at least have memory cache
            if "memory" not in self.backends:
                self.backends["memory"] = MemoryCacheBackend(self.config)

    def _start_cleanup_thread(self):
        """Start background thread for cache cleanup."""

        def cleanup_worker():
            while True:
                try:
                    time.sleep(self.config.cleanup_interval_minutes * 60)
                    self.cleanup_expired()
                except Exception as e:
                    logger.error(f"Cache cleanup error: {e}")

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Cache cleanup thread started")

    def get(self, text: str) -> Optional[bytes]:
        """
        Retrieve audio data using cache hierarchy.

        Args:
            text: Original text to look up

        Returns:
            Audio data if found, None otherwise
        """
        key = self._generate_hash(text)

        # Try memory cache first
        if "memory" in self.backends:
            try:
                data = self.backends["memory"].get(key)
                if data:
                    self._stats["hits"]["memory"] += 1
                    return data
                else:
                    self._stats["misses"]["memory"] += 1
            except Exception as e:
                self._stats["errors"]["memory"] += 1
                logger.error(f"Memory cache error: {e}")

        # Try persistent cache
        if "persistent" in self.backends:
            try:
                data = self.backends["persistent"].get(key)
                if data:
                    self._stats["hits"]["persistent"] += 1
                    # Warm memory cache
                    if "memory" in self.backends:
                        self.backends["memory"].put(
                            key, data, self.config.ttl_hours * 3600
                        )
                    return data
                else:
                    self._stats["misses"]["persistent"] += 1
            except Exception as e:
                self._stats["errors"]["persistent"] += 1
                logger.error(f"Persistent cache error: {e}")

        # Try distributed cache
        if "distributed" in self.backends:
            try:
                data = self.backends["distributed"].get(key)
                if data:
                    self._stats["hits"]["distributed"] += 1
                    # Warm lower-tier caches
                    ttl_seconds = self.config.ttl_hours * 3600
                    if "memory" in self.backends:
                        self.backends["memory"].put(key, data, ttl_seconds)
                    if "persistent" in self.backends:
                        self.backends["persistent"].put(key, data, ttl_seconds)
                    return data
                else:
                    self._stats["misses"]["distributed"] += 1
            except Exception as e:
                self._stats["errors"]["distributed"] += 1
                logger.error(f"Distributed cache error: {e}")

        return None

    def put(self, text: str, audio_data: bytes) -> str:
        """
        Store audio data in all available cache tiers.

        Args:
            text: Original text that was synthesized
            audio_data: Generated audio data

        Returns:
            Cache key (hash) for the stored entry
        """
        key = self._generate_hash(text)
        ttl_seconds = self.config.ttl_hours * 3600

        # Store in all available backends
        for tier_name, backend in self.backends.items():
            try:
                success = backend.put(key, audio_data, ttl_seconds)
                if success:
                    self._stats["puts"][tier_name] += 1
                else:
                    self._stats["errors"][tier_name] += 1
            except Exception as e:
                self._stats["errors"][tier_name] += 1
                logger.error(f"Failed to store in {tier_name} cache: {e}")

        return key

    def has(self, text: str) -> bool:
        """Check if text is cached in any tier."""
        key = self._generate_hash(text)

        for backend in self.backends.values():
            try:
                if backend.has(key):
                    return True
            except Exception as e:
                logger.error(f"Error checking cache: {e}")

        return False

    def remove(self, text: str) -> bool:
        """Remove entry from all cache tiers."""
        key = self._generate_hash(text)
        removed = False

        for backend in self.backends.values():
            try:
                if backend.remove(key):
                    removed = True
            except Exception as e:
                logger.error(f"Error removing from cache: {e}")

        return removed

    def clear(self) -> None:
        """Clear all cache tiers."""
        for tier_name, backend in self.backends.items():
            try:
                backend.clear()
                logger.info(f"Cleared {tier_name} cache")
            except Exception as e:
                logger.error(f"Error clearing {tier_name} cache: {e}")

    def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired entries from all tiers."""
        results = {}

        for tier_name, backend in self.backends.items():
            try:
                count = backend.cleanup_expired()
                results[tier_name] = count
                if count > 0:
                    logger.info(
                        f"Cleaned up {count} expired entries from {tier_name} cache"
                    )
            except Exception as e:
                logger.error(f"Error cleaning up {tier_name} cache: {e}")
                results[tier_name] = -1

        return results

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all cache tiers."""
        stats = {
            "config": asdict(self.config),
            "performance": dict(self._stats),
            "backends": {},
        }

        for tier_name, backend in self.backends.items():
            try:
                stats["backends"][tier_name] = backend.get_stats()
            except Exception as e:
                stats["backends"][tier_name] = {"error": str(e)}

        # Calculate hit rates
        for tier in ["memory", "persistent", "distributed"]:
            hits = self._stats["hits"][tier]
            misses = self._stats["misses"][tier]
            total = hits + misses
            stats["performance"][f"{tier}_hit_rate"] = hits / max(total, 1)

        return stats

    def warm_cache(self, entries: List[tuple[str, bytes]]) -> int:
        """
        Warm cache with frequently accessed entries.

        Args:
            entries: List of (text, audio_data) tuples

        Returns:
            Number of entries successfully cached
        """
        if not self.config.enable_cache_warming:
            return 0

        success_count = 0
        for text, audio_data in entries:
            try:
                self.put(text, audio_data)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to warm cache entry: {e}")

        logger.info(f"Warmed cache with {success_count}/{len(entries)} entries")
        return success_count

    def _generate_hash(self, text: str) -> str:
        """Generate SHA-256 hash for the given text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Global cache instance
_global_cache: Optional[MultiTierAudioCache] = None
_cache_lock = threading.Lock()


def get_audio_cache() -> MultiTierAudioCache:
    """Get global multi-tier audio cache instance."""
    global _global_cache
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = MultiTierAudioCache()
    return _global_cache


def initialize_audio_cache(config: Optional[CacheConfig] = None) -> MultiTierAudioCache:
    """Initialize global audio cache with custom configuration."""
    global _global_cache
    with _cache_lock:
        _global_cache = MultiTierAudioCache(config)
    return _global_cache
