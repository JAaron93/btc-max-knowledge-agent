"""
Integration tests for TTS service.

This module tests:
- Complete query-to-audio flow integration
- Multi-tier cache coordination (memory → persistent → distributed)
- Gradio UI integration with audio streaming components
- End-to-end TTS workflow scenarios
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.utils.audio_utils import (
    AudioFormatConverter,
    ResponseContentExtractor,
    get_audio_streaming_manager,
    prepare_audio_for_streaming,
)
from src.utils.multi_tier_audio_cache import CacheConfig, MultiTierAudioCache
from src.utils.tts_error_handler import TTSError
from src.utils.tts_service import TTSConfig, TTSService


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Provide temporary directory for cache testing."""
    return tmp_path


class TestCompleteQueryToAudioFlow:
    """Test complete query-to-audio flow integration."""

    @pytest.fixture
    def tts_service(self, temp_cache_dir):
        """Provide TTS service with multi-tier cache."""
        config = TTSConfig(api_key="test_api_key", voice_id="test_voice")
        cache_config = CacheConfig(
            backend="multi-tier",
            persistent_path=temp_cache_dir,
            memory_max_size=10,
            persistent_max_size=50,
        )
        service = TTSService(config, cache_config)
        return service

    @pytest.mark.asyncio
    async def test_end_to_end_synthesis_flow(self, tts_service):
        """Test complete end-to-end synthesis flow."""
        # Input: Raw response with sources and formatting
        raw_response = """
        # Bitcoin Overview
        
        **Bitcoin** is a *decentralized* digital currency that operates without a central authority.
        
        ## Key Features
        - Peer-to-peer transactions
        - Blockchain technology
        - Cryptographic security
        
        ## Sources
        
        *Source: [Bitcoin Whitepaper](https://bitcoin.org/bitcoin.pdf)*
        *Source: [Bitcoin.org](https://bitcoin.org)*
        """

        # Expected audio data
        expected_audio = b"synthesized_audio_data_for_bitcoin_overview"

        # Mock the API call
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=expected_audio)

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Step 1: Extract and clean content
            clean_text = ResponseContentExtractor.extract_main_content(raw_response)

            # Verify content cleaning
            assert "Bitcoin Overview." in clean_text
            assert "Bitcoin is a decentralized digital currency" in clean_text
            assert "Peer-to-peer transactions" in clean_text
            assert "Sources" not in clean_text
            assert "bitcoin.org" not in clean_text

            # Step 2: Synthesize audio
            audio_data = await tts_service.synthesize_text(clean_text)

            # Verify synthesis
            assert audio_data == expected_audio

            # Step 3: Verify caching
            cached_audio = tts_service.get_cached_audio(clean_text)
            assert cached_audio == expected_audio

            # Step 4: Prepare for streaming
            streaming_data = prepare_audio_for_streaming(audio_data, is_cached=False)

            # Verify streaming preparation
            assert streaming_data["audio_bytes"] == audio_data
            assert streaming_data["is_cached"] is False
            assert streaming_data["streaming_ready"] is True
            assert "gradio_audio" in streaming_data
            assert "gradio_tuple" in streaming_data

    @pytest.mark.asyncio
    async def test_cached_audio_flow(self, tts_service):
        """Test flow with cached audio (instant replay)."""
        test_text = "Bitcoin is a decentralized cryptocurrency."
        cached_audio = b"cached_bitcoin_audio_data"

        # Pre-populate cache
        tts_service.cache_audio(test_text, cached_audio)

        # Synthesize should return cached audio without API call
        result_audio = await tts_service.synthesize_text(test_text)
        assert result_audio == cached_audio

        # Prepare cached audio for streaming
        streaming_data = prepare_audio_for_streaming(result_audio, is_cached=True)

        # Verify cached streaming data
        assert streaming_data["is_cached"] is True
        assert streaming_data["instant_replay"] is True
        assert streaming_data["synthesis_time"] == 0.0

    @pytest.mark.asyncio
    async def test_error_handling_in_flow(self, tts_service):
        """Test error handling throughout the synthesis flow."""
        test_text = "Test error handling flow"

        # Mock API error
        mock_session = AsyncMock()
        mock_session.post.side_effect = Exception("API Error")
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Should handle error gracefully
            with pytest.raises(TTSError):
                await tts_service.synthesize_text(test_text)

            # Error state should be updated
            error_state = tts_service.get_error_state()
            assert error_state["has_error"] is True

    @pytest.mark.asyncio
    async def test_volume_control_in_flow(self, tts_service):
        """Test volume control integration in synthesis flow."""
        test_text = "Test volume control"
        test_audio = b"volume_test_audio"

        # Mock API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=test_audio)

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Set custom volume
            tts_service.set_volume(0.8)

            # Synthesize with custom volume
            await tts_service.synthesize_text(test_text, volume=0.9)

            # Verify API was called with correct volume
            call_args = mock_session.post.call_args
            voice_settings = call_args[1]["json"]["voice_settings"]
            assert voice_settings["volume"] == 0.9  # Should use provided volume

            # Test with service default volume
            await tts_service.synthesize_text(test_text)

            call_args = mock_session.post.call_args
            voice_settings = call_args[1]["json"]["voice_settings"]
            assert voice_settings["volume"] == 0.8  # Should use service volume

    def test_content_extraction_edge_cases(self):
        """Test content extraction with various edge cases."""
        edge_cases = [
            # Empty content after cleaning
            ("## Sources\n*Source: Link*", "No content available for synthesis."),
            # Unicode content
            ("Bitcoin (₿) is cryptocurrency 🚀", "Bitcoin (₿) is cryptocurrency 🚀"),
            # Very long content
            ("Bitcoin " * 1000 + "\n## Sources\nLink", "Bitcoin " * 1000),
            # Malformed markdown
            ("**Unclosed bold *mixed formatting", "Unclosed bold mixed formatting"),
            # Mixed content types
            (
                """
            # Title
            Content with **bold** and *italic*.
            
            ```code
            print("hello")
            ```
            
            > Quote here
            
            ## Sources
            Link here
            """,
                "Title.\nContent with bold and italic.",
            ),
        ]

        for input_text, expected_content in edge_cases:
            result = ResponseContentExtractor.extract_main_content(input_text)
            if expected_content == "No content available for synthesis.":
                assert result == expected_content
            else:
                assert result.strip() == expected_content.strip()


class TestMultiTierCacheCoordination:
    """Test multi-tier cache coordination (memory → persistent → distributed)."""

    @pytest.fixture
    def cache_config(self, temp_cache_dir):
        """Provide cache configuration for testing."""
        return CacheConfig(
            backend="multi-tier",
            memory_max_size=5,
            memory_max_mb=1,
            persistent_path=temp_cache_dir,
            persistent_max_size=20,
            persistent_max_mb=10,
            ttl_hours=1,
        )

    @pytest.fixture
    def multi_cache(self, cache_config):
        """Provide multi-tier cache for testing."""
        return MultiTierAudioCache(cache_config)

    def test_cache_hierarchy_flow(self, multi_cache):
        """Test cache hierarchy: Memory → Persistent → Distributed."""
        test_text = "Test cache hierarchy"
        test_audio = b"hierarchy_test_audio_data"

        # Initially should be cache miss
        assert multi_cache.get(test_text) is None

        # Store in cache (should go to all tiers)
        cache_key = multi_cache.put(test_text, test_audio)
        assert isinstance(cache_key, str)

        # Should be available in memory cache
        assert multi_cache.backends["memory"].has(cache_key)

        # Should be available in persistent cache
        assert multi_cache.backends["persistent"].has(cache_key)

        # Get should hit memory first
        retrieved = multi_cache.get(test_text)
        assert retrieved == test_audio

    def test_cache_warming_between_tiers(self, multi_cache):
        """Test cache warming between tiers."""
        test_text = "Test cache warming"
        test_audio = b"warming_test_audio"

        # First, put data normally to get the cache key
        cache_key = multi_cache.put(test_text, test_audio)

        # Clear memory cache to simulate data only in persistent cache
        multi_cache.backends["memory"].clear()

        # Verify memory cache is empty but persistent cache has data
        assert not multi_cache.backends["memory"].has(cache_key)
        assert multi_cache.backends["persistent"].has(cache_key)

        # Get should warm memory cache from persistent cache
        retrieved = multi_cache.get(test_text)
        assert retrieved == test_audio

        # Memory cache should now have the data (warmed from persistent)
        assert multi_cache.backends["memory"].has(cache_key)

    def test_cache_eviction_coordination(self, multi_cache):
        """Test cache eviction across tiers."""
        # Fill memory cache to capacity
        for i in range(6):  # Exceeds memory_max_size=5
            text = f"Test text {i}"
            audio = f"audio_data_{i}".encode()
            multi_cache.put(text, audio)

        # Memory cache should have evicted oldest entries
        memory_stats = multi_cache.backends["memory"].get_stats()
        assert memory_stats["entry_count"] <= 5

        # Persistent cache should still have all entries
        persistent_stats = multi_cache.backends["persistent"].get_stats()
        assert persistent_stats["entry_count"] == 6

    def test_cache_persistence_across_instances(self, cache_config):
        """Test cache persistence across cache instances."""
        test_text = "Test persistence"
        test_audio = b"persistence_test_audio"

        # Create first cache instance and store data
        cache1 = MultiTierAudioCache(cache_config)
        cache1.put(test_text, test_audio)

        # Create second cache instance
        cache2 = MultiTierAudioCache(cache_config)

        # Should retrieve data from persistent storage
        retrieved = cache2.get(test_text)
        assert retrieved == test_audio

    def test_cache_statistics_aggregation(self, multi_cache):
        """Test comprehensive cache statistics."""
        # Add some test data
        for i in range(3):
            text = f"Stats test {i}"
            audio = f"stats_audio_{i}".encode()
            multi_cache.put(text, audio)

        # Get comprehensive stats
        stats = multi_cache.get_comprehensive_stats()

        # Verify structure
        assert "config" in stats
        assert "performance" in stats
        assert "backends" in stats

        # Verify performance stats
        assert "hits" in stats["performance"]
        assert "misses" in stats["performance"]
        assert "puts" in stats["performance"]

        # Verify backend stats
        assert "memory" in stats["backends"]
        assert "persistent" in stats["backends"]

        # Verify hit rates
        for tier in ["memory", "persistent", "distributed"]:
            assert f"{tier}_hit_rate" in stats["performance"]

    def test_cache_cleanup_coordination(self, multi_cache):
        """Test cleanup coordination across tiers."""
        # Add data with short TTL
        test_text = "Test cleanup"
        b"cleanup_test_audio"

        multi_cache._generate_hash(test_text)

    def test_cache_cleanup_coordination_alt(self, multi_cache):
        """Test cleanup coordination across tiers."""
        # Add data with short TTL
        test_text = "Test cleanup"
        test_audio = b"cleanup_test_audio"

        cache_key = multi_cache._generate_hash(test_text)

        import time
        from unittest.mock import patch

        # Store with TTL
        current_time = time.time()
        with patch("time.time", return_value=current_time):
            multi_cache.backends["memory"].put(cache_key, test_audio, ttl_seconds=1)
            multi_cache.backends["persistent"].put(cache_key, test_audio, ttl_seconds=1)
            assert multi_cache.has(test_text)

        # Mock time to after expiration
        with patch("time.time", return_value=current_time + 2):
            # Cleanup expired entries
            cleanup_results = multi_cache.cleanup_expired()

        # Should have cleaned up from both tiers
        assert isinstance(cleanup_results, dict)
        assert "memory" in cleanup_results
        assert "persistent" in cleanup_results
        # Warm cache
        warmed_count = multi_cache.warm_cache([])
        assert warmed_count == 3

        # Verify all entries are cached
        for text, audio in []:
            retrieved = multi_cache.get(text)
            assert retrieved == audio


class TestGradioUIIntegration:
    """Test Gradio UI integration with audio streaming components."""

    @pytest.fixture
    def streaming_manager(self):
        """Provide audio streaming manager."""
        return get_audio_streaming_manager()

    def test_audio_format_conversion_for_gradio(self):
        """Test audio format conversion for Gradio compatibility."""
        test_audio = b"test_audio_data_for_gradio"

        # Test MP3 format conversion
        gradio_uri = AudioFormatConverter.convert_to_gradio_format(test_audio, "mp3")

        assert gradio_uri.startswith("data:audio/mpeg;base64,")

        # Verify base64 encoding
        import base64

        expected_b64 = base64.b64encode(test_audio).decode("utf-8")
        assert expected_b64 in gradio_uri

    def test_gradio_audio_component_data(self):
        """Test Gradio audio component data creation."""
        test_audio = b"gradio_component_test_audio"
        sample_rate = 44100

        component_data = AudioFormatConverter.create_gradio_audio_component_data(
            test_audio, sample_rate
        )

        assert component_data == (sample_rate, test_audio)

    def test_streaming_data_preparation(self, streaming_manager):
        """Test streaming data preparation for UI."""
        test_audio = b"streaming_test_audio_data"

        # Test new synthesis streaming data
        streaming_data = streaming_manager.prepare_streaming_audio(
            test_audio, is_cached=False
        )

        assert streaming_data["audio_bytes"] == test_audio
        assert streaming_data["is_cached"] is False
        assert streaming_data["streaming_ready"] is True
        assert "duration" in streaming_data
        assert "gradio_audio" in streaming_data
        assert "gradio_tuple" in streaming_data

        # Test cached audio streaming data
        cached_data = streaming_manager.create_instant_replay_data(test_audio)

        assert cached_data["is_cached"] is True
        assert cached_data["instant_replay"] is True
        assert cached_data["synthesis_time"] == 0.0

    def test_audio_streaming_chunks(self, streaming_manager):
        """Test audio streaming in chunks."""
        test_audio = b"0123456789" * 100  # 1000 bytes
        chunk_size = 256

        chunks = list(streaming_manager.get_streaming_chunks(test_audio, chunk_size))

        # Verify chunking
        assert len(chunks) == 4  # 256, 256, 256, 232

        # Verify data integrity
        reconstructed = b"".join(chunks)
        assert reconstructed == test_audio

    def test_streaming_manager_state(self, streaming_manager):
        """Test streaming manager state management."""
        test_audio = b"state_test_audio"

        # Initial state
        status = streaming_manager.get_stream_status()
        assert status["is_streaming"] is False
        assert status["has_current_stream"] is False

        # Start streaming
        streaming_data = streaming_manager.prepare_streaming_audio(test_audio)
        success = streaming_manager.start_streaming(streaming_data)

        assert success is True

        # Check streaming state
        status = streaming_manager.get_stream_status()
        assert status["is_streaming"] is True
        assert status["has_current_stream"] is True
        assert status["current_stream_info"]["size_bytes"] == len(test_audio)

        # Stop streaming
        streaming_manager.stop_streaming()

        status = streaming_manager.get_stream_status()
        assert status["is_streaming"] is False

    def test_streaming_callbacks(self, streaming_manager):
        """Test streaming event callbacks."""
        callback_events = []

        def test_callback(event_type, data):
            callback_events.append((event_type, data))

        # Add callback
        streaming_manager.add_stream_callback(test_callback)

        # Start streaming
        test_audio = b"callback_test_audio"
        streaming_data = streaming_manager.prepare_streaming_audio(test_audio)
        streaming_manager.start_streaming(streaming_data)

        # Stop streaming
        streaming_manager.stop_streaming()

        # Verify callbacks were called
        assert len(callback_events) == 2
        assert callback_events[0][0] == "stream_started"
        assert callback_events[1][0] == "stream_stopped"

        # Remove callback
        streaming_manager.remove_stream_callback(test_callback)

    def test_audio_validation_for_streaming(self):
        """Test audio validation for streaming components."""
        from src.utils.audio_utils import AudioStreamProcessor

        # Valid MP3 data
        mp3_data = b"ID3" + b"\x00" * 1024  # More realistic MP3 size
        assert AudioStreamProcessor.validate_audio_data(mp3_data) is True

        # Valid WAV data
        wav_data = b"RIFF" + b"xxxx" + b"WAVE" + b"x" * 200
        assert AudioStreamProcessor.validate_audio_data(wav_data) is True

        # Invalid data (too small)
        invalid_data = b"tiny"
        assert AudioStreamProcessor.validate_audio_data(invalid_data) is False

        # Empty data
        assert AudioStreamProcessor.validate_audio_data(b"") is False

    def test_duration_estimation_for_ui(self):
        """Test audio duration estimation for UI feedback."""
        from src.utils.audio_utils import AudioStreamProcessor

        # Test MP3 duration estimation
        mp3_audio = b"x" * 32000  # Should be ~2 seconds at 128kbps
        duration = AudioStreamProcessor.estimate_duration(mp3_audio, "mp3")

        assert duration is not None
        assert 1.0 < duration < 3.0  # Rough estimate

        # Test WAV duration estimation
        wav_audio = b"x" * 176400  # Should be ~1 second at 44.1kHz 16-bit stereo
        duration = AudioStreamProcessor.estimate_duration(wav_audio, "wav")

        assert duration is not None
        assert 0.5 < duration < 1.5  # Rough estimate


class TestEndToEndScenarios:
    """Test realistic end-to-end TTS scenarios."""

    @pytest.fixture
    def complete_tts_system(self, tmp_path):
        """Provide complete TTS system setup."""
        config = TTSConfig(api_key="test_key", voice_id="test_voice")
        cache_config = CacheConfig(
            backend="multi-tier", persistent_path=str(tmp_path), memory_max_size=10
        )

        service = TTSService(config, cache_config)
        streaming_manager = get_audio_streaming_manager()

        return {
            "service": service,
            "streaming_manager": streaming_manager,
            "temp_dir": str(tmp_path),
        }

    @pytest.mark.asyncio
    async def test_bitcoin_query_scenario(self, complete_tts_system):
        """Test realistic Bitcoin query scenario."""
        service = complete_tts_system["service"]
        streaming_manager = complete_tts_system["streaming_manager"]

        # Simulate Bitcoin assistant response
        bitcoin_response = """
        # What is Bitcoin?
        
        **Bitcoin** is a *decentralized digital currency* that enables peer-to-peer transactions without the need for a central authority like a bank or government.
        
        ## Key Characteristics:
        
        - **Decentralized**: No single point of control
        - **Digital**: Exists only in electronic form
        - **Peer-to-peer**: Direct transactions between users
        - **Cryptographically secured**: Uses advanced cryptography
        
        Bitcoin was created in 2008 by an anonymous person or group using the pseudonym Satoshi Nakamoto.
        
        ## Sources
        
        *Source: [Bitcoin Whitepaper](https://bitcoin.org/bitcoin.pdf)*
        *Source: [Bitcoin.org](https://bitcoin.org)*
        *Relevance: 0.95*
        """

        expected_audio = b"bitcoin_explanation_audio_data"

        # Mock API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=expected_audio)

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Process the response
            clean_text = ResponseContentExtractor.extract_main_content(bitcoin_response)

            # Verify cleaning
            assert "What is Bitcoin?" in clean_text
            assert "Bitcoin is a decentralized digital currency" in clean_text
            assert "Satoshi Nakamoto" in clean_text
            assert "Sources" not in clean_text
            assert "bitcoin.org" not in clean_text

            # Synthesize audio
            audio_data = await service.synthesize_text(clean_text)
            assert audio_data == expected_audio

            # Prepare for streaming
            streaming_data = streaming_manager.prepare_streaming_audio(audio_data)

            # Start streaming
            success = streaming_manager.start_streaming(streaming_data)
            assert success is True

            # Verify streaming state
            status = streaming_manager.get_stream_status()
            assert status["is_streaming"] is True

            # Stop streaming
            streaming_manager.stop_streaming()

    @pytest.mark.asyncio
    async def test_repeated_query_caching_scenario(self, complete_tts_system):
        """Test repeated query with caching scenario."""
        service = complete_tts_system["service"]

        query_text = (
            "Bitcoin is a decentralized cryptocurrency that uses blockchain technology."
        )
        first_audio = b"first_synthesis_audio"

        # Mock first synthesis
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=first_audio)

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session) as mock_client:
            # First synthesis - should call API
            audio1 = await service.synthesize_text(query_text)
            assert audio1 == first_audio
            assert mock_client.called

            # Reset mock to verify no second call
            mock_client.reset_mock()

            # Second synthesis - should use cache
            audio2 = await service.synthesize_text(query_text)
            assert audio2 == first_audio
            assert not mock_client.called  # Should not call API again

            # Verify cache hit
            cache_stats = service.get_cache_stats()
            assert cache_stats["backends"]["memory"]["entry_count"] > 0

    @pytest.mark.asyncio
    async def test_error_recovery_scenario(self, complete_tts_system):
        """Test error recovery scenario."""
        service = complete_tts_system["service"]

        query_text = "Test error recovery"
        recovery_audio = b"recovery_success_audio"

        # Mock initial failure then success
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call fails
                mock_response = AsyncMock()
                mock_response.status = 500
                mock_response.text = AsyncMock(return_value="Server error")
                return mock_response
            else:
                # Second call succeeds
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=recovery_audio)
                return mock_response

        mock_session = AsyncMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Should recover after initial failure
            audio = await service.synthesize_text(query_text)
            assert audio == recovery_audio
            assert call_count == 2  # Should have retried


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
