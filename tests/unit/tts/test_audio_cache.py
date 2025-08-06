"""
Unit tests for the audio caching system.

Tests cover cache hit/miss scenarios, memory management, LRU eviction,
and various edge cases.
"""

import hashlib
from datetime import datetime
from unittest.mock import patch


from btc_max_knowledge_agent.utils.audio_cache import AudioCache, CacheEntry


class TestCacheEntry:
    """Test CacheEntry dataclass functionality."""

    def test_cache_entry_creation(self):
        """Test basic cache entry creation with automatic size calculation."""
        audio_data = b"test audio data"
        entry = CacheEntry(
            text_hash="test_hash",
            audio_data=audio_data,
            timestamp=datetime.now(),
            access_count=0,
            # size_bytes not provided - should be calculated automatically
        )

        assert entry.text_hash == "test_hash"
        assert entry.audio_data == audio_data
        assert entry.access_count == 0
        assert entry.size_bytes == len(audio_data)

    def test_cache_entry_with_explicit_size(self):
        """Test cache entry with explicitly set size."""
        audio_data = b"test audio data"
        explicit_size = 100
        entry = CacheEntry(
            text_hash="test_hash",
            audio_data=audio_data,
            timestamp=datetime.now(),
            access_count=5,
            size_bytes=explicit_size,
        )

        assert entry.size_bytes == explicit_size  # Should not be overridden

    def test_cache_entry_with_zero_size(self):
        """Test cache entry with explicitly set zero size (should be preserved)."""
        audio_data = b"test audio data"
        entry = CacheEntry(
            text_hash="test_hash",
            audio_data=audio_data,
            timestamp=datetime.now(),
            access_count=0,
            size_bytes=0,  # Explicitly set to 0 - should be preserved
        )

        assert entry.size_bytes == 0  # Should not be overridden to len(audio_data)


class TestAudioCache:
    """Test AudioCache functionality."""

    def test_cache_initialization(self):
        """Test cache initialization with default and custom parameters."""
        # Default initialization
        cache = AudioCache()
        assert cache.max_size == 100
        assert cache.max_memory_bytes == 50 * 1024 * 1024
        assert len(cache) == 0

        # Custom initialization
        cache = AudioCache(max_size=50, max_memory_mb=25)
        assert cache.max_size == 50
        assert cache.max_memory_bytes == 25 * 1024 * 1024

    def test_hash_generation(self):
        """Test SHA-256 hash generation."""
        cache = AudioCache()
        text = "Hello, world!"
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        generated_hash = cache._generate_hash(text)
        assert generated_hash == expected_hash

        # Test consistency
        assert cache._generate_hash(text) == cache._generate_hash(text)

        # Test different texts produce different hashes
        assert cache._generate_hash("text1") != cache._generate_hash("text2")

    def test_basic_put_and_get(self):
        """Test basic cache put and get operations."""
        cache = AudioCache()
        text = "Test response text"
        audio_data = b"fake audio data"

        # Put data in cache
        cache_key = cache.put(text, audio_data)
        assert isinstance(cache_key, str)
        assert len(cache_key) == 64  # SHA-256 hex length

        # Get data from cache
        retrieved_data = cache.get(text)
        assert retrieved_data == audio_data

        # Test cache hit
        assert cache.has(text)
        assert text in cache
        assert len(cache) == 1

    def test_cache_miss(self):
        """Test cache miss scenarios."""
        cache = AudioCache()

        # Test get on empty cache
        assert cache.get("nonexistent text") is None
        assert not cache.has("nonexistent text")
        assert "nonexistent text" not in cache

        # Add one item and test miss on different text
        cache.put("existing text", b"audio data")
        assert cache.get("different text") is None
        assert not cache.has("different text")

    def test_get_by_hash(self):
        """Test getting cached data by hash."""
        cache = AudioCache()
        text = "Test text"
        audio_data = b"test audio"

        cache_key = cache.put(text, audio_data)

        # Get by hash
        retrieved_data = cache.get_by_hash(cache_key)
        assert retrieved_data == audio_data

        # Test has_hash
        assert cache.has_hash(cache_key)

        # Test miss by hash
        fake_hash = "a" * 64
        assert cache.get_by_hash(fake_hash) is None
        assert not cache.has_hash(fake_hash)

    def test_lru_eviction_by_count(self):
        """Test LRU eviction when max_size is exceeded."""
        cache = AudioCache(max_size=3)

        # Add 3 items (at limit)
        cache.put("text1", b"audio1")
        cache.put("text2", b"audio2")
        cache.put("text3", b"audio3")
        assert len(cache) == 3

        # Add 4th item, should evict oldest (text1)
        cache.put("text4", b"audio4")
        assert len(cache) == 3
        assert not cache.has("text1")  # Should be evicted
        assert cache.has("text2")
        assert cache.has("text3")
        assert cache.has("text4")

        # Access text2 to make it most recent
        cache.get("text2")

        # Add 5th item, should evict text3 (now oldest)
        cache.put("text5", b"audio5")
        assert len(cache) == 3
        assert not cache.has("text3")  # Should be evicted
        assert cache.has("text2")  # Should remain (recently accessed)
        assert cache.has("text4")
        assert cache.has("text5")

    def test_lru_eviction_by_memory(self):
        """Test LRU eviction when memory limit is exceeded."""
        # Set very small memory limit (1KB)
        cache = AudioCache(max_size=100, max_memory_mb=0.001)

        # Add large audio data that exceeds memory limit
        large_audio1 = b"x" * 600  # 600 bytes
        large_audio2 = b"y" * 600  # 600 bytes

        cache.put("text1", large_audio1)
        assert cache.has("text1")

        # Adding second large item should evict first due to memory limit
        cache.put("text2", large_audio2)
        assert not cache.has("text1")  # Should be evicted
        assert cache.has("text2")
        assert len(cache) == 1

    def test_cache_update_existing_entry(self):
        """Test updating an existing cache entry."""
        cache = AudioCache()
        text = "same text"
        audio_data1 = b"first audio"
        audio_data2 = b"second audio"

        # Add initial entry
        key1 = cache.put(text, audio_data1)
        assert cache.get(text) == audio_data1
        assert len(cache) == 1

        # Update with new audio data
        key2 = cache.put(text, audio_data2)
        assert key1 == key2  # Same hash for same text
        assert cache.get(text) == audio_data2  # Should have new data
        assert len(cache) == 1  # Should still be only one entry

    def test_access_count_tracking(self):
        """Test that access counts are properly tracked."""
        cache = AudioCache()
        text = "test text"
        audio_data = b"test audio"

        cache.put(text, audio_data)

        # Initial access count should be 0
        stats = cache.get_stats()
        assert stats["entries"][0]["access_count"] == 0

        # Access the entry multiple times
        cache.get(text)
        cache.get(text)
        cache.get(text)

        # Check access count increased
        stats = cache.get_stats()
        assert stats["entries"][0]["access_count"] == 3

    def test_remove_operations(self):
        """Test cache removal operations."""
        cache = AudioCache()
        text1 = "text1"
        text2 = "text2"
        audio1 = b"audio1"
        audio2 = b"audio2"

        cache.put(text1, audio1)
        key2 = cache.put(text2, audio2)
        assert len(cache) == 2

        # Remove by text
        assert cache.remove(text1)
        assert not cache.has(text1)
        assert cache.has(text2)
        assert len(cache) == 1

        # Remove by hash
        assert cache.remove_by_hash(key2)
        assert not cache.has(text2)
        assert len(cache) == 0

        # Test removing non-existent entries
        assert not cache.remove("nonexistent")
        assert not cache.remove_by_hash("fake_hash")

    def test_clear_cache(self):
        """Test clearing all cache entries."""
        cache = AudioCache()

        # Add multiple entries
        cache.put("text1", b"audio1")
        cache.put("text2", b"audio2")
        cache.put("text3", b"audio3")
        assert len(cache) == 3

        # Clear cache
        cache.clear()
        assert len(cache) == 0
        stats = cache.get_stats()
        assert stats["total_size_bytes"] == 0
        assert not cache.has("text1")
        assert not cache.has("text2")
        assert not cache.has("text3")

    def test_cache_stats(self):
        """Test cache statistics reporting."""
        cache = AudioCache(max_size=10, max_memory_mb=1)

        # Empty cache stats
        stats = cache.get_stats()
        assert stats["entry_count"] == 0
        assert stats["max_size"] == 10
        assert stats["total_size_bytes"] == 0
        assert stats["max_memory_bytes"] == 1024 * 1024
        assert stats["memory_usage_percent"] == 0
        assert stats["entries"] == []

        # Add some entries
        audio_data = b"test audio data"
        cache.put("text1", audio_data)
        cache.put("text2", audio_data)

        stats = cache.get_stats()
        assert stats["entry_count"] == 2
        assert stats["total_size_bytes"] == len(audio_data) * 2
        assert stats["memory_usage_percent"] > 0
        assert len(stats["entries"]) == 2

        # Check entry details
        entry = stats["entries"][0]
        assert "hash" in entry
        assert "size_bytes" in entry
        assert "access_count" in entry
        assert "timestamp" in entry
        assert entry["size_bytes"] == len(audio_data)

    def test_memory_tracking(self):
        """Test accurate memory usage tracking."""
        cache = AudioCache()

        assert cache._total_size_bytes == 0

        # Add entries and check memory tracking
        audio1 = b"x" * 100
        audio2 = b"y" * 200

        cache.put("text1", audio1)
        assert cache._total_size_bytes == 100

        cache.put("text2", audio2)
        assert cache._total_size_bytes == 300

        # Remove entry and check memory tracking
        cache.remove("text1")
        assert cache._total_size_bytes == 200

        # Clear and check memory tracking
        cache.clear()
        assert cache._total_size_bytes == 0

    def test_edge_cases(self):
        """Test various edge cases."""
        cache = AudioCache()

        # Empty text
        cache.put("", b"audio for empty text")
        assert cache.has("")
        assert cache.get("") == b"audio for empty text"

        # Empty audio data
        cache.put("text for empty audio", b"")
        assert cache.has("text for empty audio")
        assert cache.get("text for empty audio") == b""

        # Very long text
        long_text = "x" * 10000
        cache.put(long_text, b"audio for long text")
        assert cache.has(long_text)

        # Unicode text
        unicode_text = "Hello 世界 🌍"
        cache.put(unicode_text, b"unicode audio")
        assert cache.has(unicode_text)
        assert cache.get(unicode_text) == b"unicode audio"

    def test_concurrent_access_simulation(self):
        """Test behavior under simulated concurrent access patterns."""
        cache = AudioCache(max_size=5)

        # Simulate multiple accesses to same entries
        texts = ["text1", "text2", "text3"]
        for text in texts:
            cache.put(text, f"audio_{text}".encode())

        # Simulate access pattern that should affect LRU order
        cache.get("text1")  # Make text1 most recent
        cache.get("text3")  # Make text3 second most recent
        # text2 is now least recent

        # Add new entries to trigger eviction
        cache.put("text4", b"audio4")
        cache.put("text5", b"audio5")
        cache.put("text6", b"audio6")  # Should evict text2

        assert cache.has("text1")  # Should remain (recently accessed)
        assert not cache.has("text2")  # Should be evicted (least recent)
        assert cache.has("text3")  # Should remain (recently accessed)
        assert cache.has("text4")
        assert cache.has("text5")


class TestAudioCacheIntegration:
    """Integration tests for audio cache with realistic scenarios."""

    def test_realistic_tts_workflow(self):
        """Test cache behavior in realistic TTS workflow."""
        cache = AudioCache(max_size=10)

        # Simulate typical user interactions
        responses = [
            "Bitcoin is a decentralized digital currency.",
            "The Lightning Network is a layer-2 scaling solution.",
            "Bitcoin mining secures the network through proof-of-work.",
            "Bitcoin is a decentralized digital currency.",  # Repeat
        ]

        audio_files = [f"audio_data_{i}".encode() for i in range(len(responses))]

        # First pass - cache misses
        for i, response in enumerate(responses[:3]):
            assert not cache.has(response)
            cache.put(response, audio_files[i])
            assert cache.has(response)

        # Fourth response is repeat - should be cache hit
        assert cache.has(responses[3])
        cached_audio = cache.get(responses[3])
        assert cached_audio == audio_files[0]  # Same as first response

        # Verify cache state
        assert len(cache) == 3  # Only 3 unique responses
        stats = cache.get_stats()
        assert stats["entry_count"] == 3

    def test_memory_pressure_scenario(self):
        """Test cache behavior under memory pressure."""
        # Small cache for testing memory limits
        cache = AudioCache(max_size=100, max_memory_mb=0.01)  # 10KB limit

        # Generate responses with varying audio sizes
        small_audio = b"x" * 1000  # 1KB
        medium_audio = b"y" * 5000  # 5KB
        large_audio = b"z" * 8000  # 8KB

        # Add small audio - should fit
        cache.put("small response", small_audio)
        assert cache.has("small response")

        # Add medium audio - should fit together
        cache.put("medium response", medium_audio)
        assert cache.has("small response")
        assert cache.has("medium response")

        # Add large audio - should evict others due to memory limit
        cache.put("large response", large_audio)
        assert cache.has("large response")
        # Previous entries should be evicted due to memory pressure
        # Only the large response should remain due to memory limit
        assert len(cache) == 1
        assert not cache.has("small response")
        assert not cache.has("medium response")

    @patch("btc_max_knowledge_agent.utils.audio_cache.logger")
    def test_logging_behavior(self, mock_logger):
        """Test that appropriate logging occurs."""
        cache = AudioCache(max_size=2)

        # Test cache operations generate appropriate logs
        cache.put("text1", b"audio1")
        cache.put("text2", b"audio2")
        cache.put("text3", b"audio3")  # Should trigger eviction

        # Verify logging calls were made
        assert mock_logger.debug.called
        assert mock_logger.info.called

        # Test cache clear logging
        cache.clear()
        mock_logger.info.assert_called_with("Cleared 2 cache entries")
