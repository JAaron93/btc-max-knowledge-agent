#!/usr/bin/env python3
"""
Test script for multi-tier audio cache implementation.

This script demonstrates and tests the multi-tier caching system
with memory, persistent (SQLite), and distributed (Redis) backends.
"""

import os
import sys
import asyncio
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.multi_tier_audio_cache import (
    MultiTierAudioCache, 
    CacheConfig, 
    MemoryCacheBackend,
    SQLiteCacheBackend
)
from utils.tts_service import TTSService, TTSConfig


def test_cache_backends():
    """Test individual cache backends."""
    print("=== Testing Cache Backends ===")
    
    # Test memory cache
    print("\n1. Testing Memory Cache Backend:")
    config = CacheConfig(backend="memory")
    memory_cache = MemoryCacheBackend(config)
    
    test_key = "test_hash_123"
    test_data = b"fake audio data for testing"
    
    # Test put/get
    success = memory_cache.put(test_key, test_data, ttl_seconds=3600)
    print(f"   Put operation: {'SUCCESS' if success else 'FAILED'}")
    
    retrieved = memory_cache.get(test_key)
    print(f"   Get operation: {'SUCCESS' if retrieved == test_data else 'FAILED'}")
    
    # Test has
    exists = memory_cache.has(test_key)
    print(f"   Has operation: {'SUCCESS' if exists else 'FAILED'}")
    
    # Test stats
    stats = memory_cache.get_stats()
    print(f"   Stats: {stats['entry_count']} entries, {stats['total_size_bytes']} bytes")
    
    # Test SQLite cache
    print("\n2. Testing SQLite Cache Backend:")
    sqlite_config = CacheConfig(backend="sqlite", persistent_path="./test_cache")
    sqlite_cache = SQLiteCacheBackend(sqlite_config)
    
    # Test put/get
    success = sqlite_cache.put(test_key, test_data, ttl_seconds=3600)
    print(f"   Put operation: {'SUCCESS' if success else 'FAILED'}")
    
    retrieved = sqlite_cache.get(test_key)
    print(f"   Get operation: {'SUCCESS' if retrieved == test_data else 'FAILED'}")
    
    # Test stats
    stats = sqlite_cache.get_stats()
    print(f"   Stats: {stats['entry_count']} entries, {stats['total_size_bytes']} bytes")
    
    # Cleanup
    sqlite_cache.clear()


def test_multi_tier_cache():
    """Test multi-tier cache coordination."""
    print("\n=== Testing Multi-Tier Cache ===")
    
    # Configure for multi-tier with memory + SQLite
    config = CacheConfig(
        backend="multi-tier",
        memory_max_size=10,
        memory_max_mb=1,
        persistent_path="./test_cache",
        ttl_hours=1
    )
    
    cache = MultiTierAudioCache(config)
    
    # Test data
    test_texts = [
        "Hello, this is a test message for caching.",
        "Another test message with different content.",
        "Third message to test cache hierarchy."
    ]
    
    fake_audio_data = [
        b"fake_audio_data_1" * 100,
        b"fake_audio_data_2" * 150,
        b"fake_audio_data_3" * 200
    ]
    
    print("\n1. Testing cache hierarchy (put operations):")
    for i, (text, audio) in enumerate(zip(test_texts, fake_audio_data)):
        cache_key = cache.put(text, audio)
        print(f"   Cached text {i+1}: {cache_key[:8]}... ({len(audio)} bytes)")
    
    print("\n2. Testing cache hierarchy (get operations):")
    for i, text in enumerate(test_texts):
        start_time = time.time()
        retrieved = cache.get(text)
        end_time = time.time()
        
        success = retrieved == fake_audio_data[i]
        print(f"   Retrieved text {i+1}: {'SUCCESS' if success else 'FAILED'} ({(end_time - start_time)*1000:.2f}ms)")
    
    print("\n3. Cache statistics:")
    stats = cache.get_comprehensive_stats()
    
    print(f"   Configuration: {stats['config']['backend']}")
    print(f"   Performance stats:")
    for tier in ['memory', 'persistent', 'distributed']:
        hits = stats['performance']['hits'][tier]
        misses = stats['performance']['misses'][tier]
        hit_rate = stats['performance'].get(f'{tier}_hit_rate', 0)
        print(f"     {tier.capitalize()}: {hits} hits, {misses} misses, {hit_rate:.2%} hit rate")
    
    print(f"   Backend stats:")
    for tier, backend_stats in stats['backends'].items():
        if 'error' not in backend_stats:
            entries = backend_stats.get('entry_count', 0)
            size = backend_stats.get('total_size_bytes', 0)
            print(f"     {tier.capitalize()}: {entries} entries, {size} bytes")
    
    # Test cache warming
    print("\n4. Testing cache warming:")
    warm_entries = [
        ("Warm cache entry 1", b"warm_audio_1" * 50),
        ("Warm cache entry 2", b"warm_audio_2" * 75)
    ]
    
    warmed_count = cache.warm_cache(warm_entries)
    print(f"   Warmed {warmed_count}/{len(warm_entries)} entries")
    
    # Test cleanup
    print("\n5. Testing cache cleanup:")
    cleanup_results = cache.cleanup_expired()
    print(f"   Cleanup results: {cleanup_results}")


async def test_tts_integration():
    """Test TTS service integration with multi-tier cache."""
    print("\n=== Testing TTS Service Integration ===")
    
    # Check if API key is available
    api_key = os.getenv("ELEVEN_LABS_API_KEY")
    if not api_key:
        print("   SKIPPED: ELEVEN_LABS_API_KEY not found in environment")
        return
    
    # Configure TTS service
    tts_config = TTSConfig(api_key=api_key, enabled=True)
    tts_service = TTSService(tts_config)
    
    if not tts_service.is_enabled():
        print("   SKIPPED: TTS service not enabled")
        return
    
    test_text = "This is a test message for TTS caching integration."
    
    print(f"\n1. Testing TTS synthesis with caching:")
    print(f"   Text: '{test_text[:50]}...'")
    
    try:
        # First synthesis (should hit API)
        start_time = time.time()
        audio_data = await tts_service.synthesize_text(test_text)
        first_time = time.time() - start_time
        
        print(f"   First synthesis: {len(audio_data)} bytes in {first_time:.2f}s")
        
        # Second synthesis (should hit cache)
        start_time = time.time()
        cached_audio = await tts_service.synthesize_text(test_text)
        second_time = time.time() - start_time
        
        print(f"   Second synthesis: {len(cached_audio)} bytes in {second_time:.2f}s")
        print(f"   Cache speedup: {first_time/second_time:.1f}x faster")
        
        # Verify data consistency
        if audio_data == cached_audio:
            print("   Data consistency: SUCCESS")
        else:
            print("   Data consistency: FAILED")
        
        # Show cache stats
        print(f"\n2. TTS Cache Statistics:")
        stats = tts_service.get_cache_stats()
        
        for tier, backend_stats in stats['backends'].items():
            if 'error' not in backend_stats:
                entries = backend_stats.get('entry_count', 0)
                size = backend_stats.get('total_size_bytes', 0)
                print(f"   {tier.capitalize()}: {entries} entries, {size:,} bytes")
    
    except Exception as e:
        print(f"   ERROR: {e}")


def main():
    """Run all tests."""
    print("Multi-Tier Audio Cache Test Suite")
    print("=" * 50)
    
    try:
        # Test individual backends
        test_cache_backends()
        
        # Test multi-tier coordination
        test_multi_tier_cache()
        
        # Test TTS integration
        asyncio.run(test_tts_integration())
        
        print("\n" + "=" * 50)
        print("All tests completed!")
        
    except Exception as e:
        print(f"\nTest suite failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup test files
        import shutil
        test_cache_dir = Path("./test_cache")
        if test_cache_dir.exists():
            shutil.rmtree(test_cache_dir)
            print("Cleaned up test cache directory")


if __name__ == "__main__":
    main()