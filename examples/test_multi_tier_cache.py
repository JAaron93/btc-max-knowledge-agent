#!/usr/bin/env python3
"""
Test script for multi-tier audio cache implementation.

This script demonstrates and tests the multi-tier caching system
with memory, persistent (SQLite), and distributed (Redis) backends.
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add src to path for imports (must be before local package imports)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# flake8: noqa: E402 - Allow imports after sys.path modification for examples script
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from project_name.utils.multi_tier_audio_cache import (  # noqa: F401
        CacheConfig as _CacheConfig,
    )
    from project_name.utils.multi_tier_audio_cache import (  # noqa: F401
        MemoryCacheBackend as _MemoryCacheBackend,
    )
    from project_name.utils.multi_tier_audio_cache import (  # noqa: F401
        MultiTierAudioCache as _MultiTierAudioCache,
    )
    from project_name.utils.multi_tier_audio_cache import (  # noqa: F401
        SQLiteCacheBackend as _SQLiteCacheBackend,
    )

    from utils.tts_service import TTSConfig as _TTSConfig  # noqa: F401
    from utils.tts_service import TTSService as _TTSService  # noqa: F401

# Runtime imports (may not be available to type checkers)
from project_name.utils.multi_tier_audio_cache import (  # type: ignore[import-not-found]  # adjust to real package root
    CacheConfig,
    MemoryCacheBackend,
    MultiTierAudioCache,
    SQLiteCacheBackend,
)

from utils.tts_service import (  # type: ignore[import-not-found]
    TTSConfig,
    TTSService,
)

# Basic logging configuration for example/test usage.
# Using INFO level so performance stats and diagnostics are visible by default.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def test_cache_backends():
    """Test individual cache backends."""
    logging.info("=== Testing Cache Backends ===")

    # Test memory cache
    logging.info("1. Testing Memory Cache Backend:")
    config = CacheConfig(backend="memory")
    memory_cache = MemoryCacheBackend(config)

    test_key = "test_hash_123"
    test_data = b"fake audio data for testing"

    # Test put/get
    success = memory_cache.put(test_key, test_data, ttl_seconds=3600)
    logging.info("   Put operation: %s", "SUCCESS" if success else "FAILED")

    retrieved = memory_cache.get(test_key)
    logging.info(
        "   Get operation: %s",
        "SUCCESS" if retrieved == test_data else "FAILED",
    )

    # Test has
    exists = memory_cache.has(test_key)
    logging.info("   Has operation: %s", "SUCCESS" if exists else "FAILED")

    # Test stats
    stats = memory_cache.get_stats()
    logging.info(
        "   Stats: %s entries, %s bytes",
        stats.get("entry_count"),
        stats.get("total_size_bytes"),
    )

    # Test SQLite cache
    logging.info("2. Testing SQLite Cache Backend:")
    sqlite_config = CacheConfig(
        backend="sqlite",
        persistent_path="./test_cache",
    )
    sqlite_cache = SQLiteCacheBackend(sqlite_config)

    # Test put/get
    success = sqlite_cache.put(test_key, test_data, ttl_seconds=3600)
    logging.info("   Put operation: %s", "SUCCESS" if success else "FAILED")

    retrieved = sqlite_cache.get(test_key)
    logging.info(
        "   Get operation: %s",
        "SUCCESS" if retrieved == test_data else "FAILED",
    )

    # Test stats
    stats = sqlite_cache.get_stats()
    logging.info(
        "   Stats: %s entries, %s bytes",
        stats.get("entry_count"),
        stats.get("total_size_bytes"),
    )

    # Cleanup
    sqlite_cache.clear()


def test_multi_tier_cache():
    """Test multi-tier cache coordination."""
    logging.info("=== Testing Multi-Tier Cache ===")

    # Configure for multi-tier with memory + SQLite
    config = CacheConfig(
        backend="multi-tier",
        memory_max_size=10,
        memory_max_mb=1,
        persistent_path="./test_cache",
        ttl_hours=1,
    )

    cache = MultiTierAudioCache(config)

    # Test data
    test_texts = [
        "Hello, this is a test message for caching.",
        "Another test message with different content.",
        "Third message to test cache hierarchy.",
    ]

    fake_audio_data = [
        b"fake_audio_data_1" * 100,
        b"fake_audio_data_2" * 150,
        b"fake_audio_data_3" * 200,
    ]

    logging.info("1. Testing cache hierarchy (put operations):")
    for i, (text, audio) in enumerate(zip(test_texts, fake_audio_data)):
        cache_key = cache.put(text, audio)
        logging.info(
            "   Cached text %s: %s... (%s bytes)",
            i + 1,
            cache_key[:8],
            len(audio),
        )

    logging.info("2. Testing cache hierarchy (get operations):")
    for i, text in enumerate(test_texts):
        start_time = time.time()
        retrieved = cache.get(text)
        end_time = time.time()

        success = retrieved == fake_audio_data[i]
        logging.info(
            "   Retrieved text %s: %s (%.2fms)",
            i + 1,
            "SUCCESS" if success else "FAILED",
            (end_time - start_time) * 1000,
        )

    logging.info("3. Cache statistics:")
    stats = cache.get_comprehensive_stats()

    logging.info("   Configuration: %s", stats["config"]["backend"])
    logging.info("   Performance stats:")
    for tier in ["memory", "persistent", "distributed"]:
        hits = stats["performance"]["hits"][tier]
        misses = stats["performance"]["misses"][tier]
        hit_rate = stats["performance"].get(f"{tier}_hit_rate", 0)
        logging.info(
            "     %s: %s hits, %s misses, %.2f%% hit rate",
            tier.capitalize(),
            hits,
            misses,
            hit_rate * 100,
        )

    logging.info("   Backend stats:")
    for tier, backend_stats in stats["backends"].items():
        if "error" not in backend_stats:
            entries = backend_stats.get("entry_count", 0)
            size = backend_stats.get("total_size_bytes", 0)
            logging.info(
                "     %s: %s entries, %s bytes",
                tier.capitalize(),
                entries,
                size,
            )

    # Test cache warming
    logging.info("4. Testing cache warming:")
    warm_entries = [
        ("Warm cache entry 1", b"warm_audio_1" * 50),
        ("Warm cache entry 2", b"warm_audio_2" * 75),
    ]

    warmed_count = cache.warm_cache(warm_entries)
    logging.info("   Warmed %s/%s entries", warmed_count, len(warm_entries))

    # Test cleanup
    logging.info("5. Testing cache cleanup:")
    cleanup_results = cache.cleanup_expired()
    logging.info("   Cleanup results: %s", cleanup_results)


async def test_tts_integration():
    """Test TTS service integration with multi-tier cache."""
    logging.info("=== Testing TTS Service Integration ===")

    # Check if API key is available
    api_key = os.getenv("ELEVEN_LABS_API_KEY")
    if not api_key:
        logging.info("   SKIPPED: ELEVEN_LABS_API_KEY not found in environment")
        return

    # Configure TTS service
    tts_config = TTSConfig(api_key=api_key, enabled=True)
    tts_service = TTSService(tts_config)

    if not tts_service.is_enabled():
        logging.info("   SKIPPED: TTS service not enabled")
        return

    test_text = "This is a test message for TTS caching integration."

    logging.info("1. Testing TTS synthesis with caching:")
    logging.info("   Text: '%s...'", test_text[:50])

    try:
        # First synthesis (should hit API)
        start_time = time.time()
        audio_data = await tts_service.synthesize_text(test_text)
        first_time = time.time() - start_time

        logging.info(
            "   First synthesis: %s bytes in %.2fs",
            len(audio_data),
            first_time,
        )

        # Second synthesis (should hit cache)
        start_time = time.time()
        cached_audio = await tts_service.synthesize_text(test_text)
        second_time = time.time() - start_time

        logging.info(
            "   Second synthesis: %s bytes in %.2fs", len(cached_audio), second_time
        )
        logging.info(
            "   Cache speedup: %.1fx faster", first_time / max(second_time, 1e-9)
        )

        # Verify data consistency
        if audio_data == cached_audio:
            logging.info("   Data consistency: SUCCESS")
        else:
            logging.info("   Data consistency: FAILED")

        # Show cache stats
        logging.info("2. TTS Cache Statistics:")
        stats = tts_service.get_cache_stats()

        for tier, backend_stats in stats["backends"].items():
            if "error" not in backend_stats:
                entries = backend_stats.get("entry_count", 0)
                size = backend_stats.get("total_size_bytes", 0)
                logging.info(
                    "   %s: %s entries, %s bytes",
                    tier.capitalize(),
                    entries,
                    f"{size:,}",
                )

    except Exception as e:
        logging.exception("   ERROR during TTS integration: %s", e)


def main():
    """Run all tests."""
    logging.info("Multi-Tier Audio Cache Test Suite")
    logging.info("=" * 50)

    try:
        # Test individual backends
        test_cache_backends()

        # Test multi-tier coordination
        test_multi_tier_cache()

        # Test TTS integration
        asyncio.run(test_tts_integration())

        logging.info("=" * 50)
        logging.info("All tests completed!")

    except Exception as e:
        logging.exception("Test suite failed with error: %s", e)

    finally:
        # Cleanup test files
        import shutil

        test_cache_dir = Path("./test_cache")
        if test_cache_dir.exists():
            shutil.rmtree(test_cache_dir)
            logging.info("Cleaned up test cache directory")


if __name__ == "__main__":
    main()
