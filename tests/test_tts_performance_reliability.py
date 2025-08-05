"""
Performance and reliability tests for TTS service.

This module tests:
- Audio streaming performance with various buffer sizes
- System behavior under network latency and packet loss
- Recovery mechanisms after temporary service outages
- Performance optimization validation
- Reliability under adverse conditions
"""

import asyncio
import shutil
import tempfile
import threading
import time
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from src.utils.audio_utils import (AudioFormatConverter, AudioStreamingManager,
                                   AudioStreamProcessor,
                                   get_audio_streaming_manager)
from src.utils.multi_tier_audio_cache import CacheConfig, MultiTierAudioCache
from src.utils.tts_error_handler import (TTSErrorHandler, TTSNetworkError,
                                         TTSServerError)
from src.utils.tts_service import TTSConfig, TTSService


class TestAudioStreamingPerformance:
    """Test audio streaming performance with various buffer sizes."""

    @pytest.fixture
    def streaming_manager(self):
        """Provide audio streaming manager for testing."""
        return get_audio_streaming_manager()

    def test_streaming_chunk_sizes(self, streaming_manager):
        """Test streaming performance with different chunk sizes."""
        test_audio = b"0123456789" * 1000  # 10KB audio data
        chunk_sizes = [512, 1024, 2048, 4096, 8192]

        performance_results = {}

        for chunk_size in chunk_sizes:
            start_time = time.time()

            # Generate chunks
            chunks = list(
                streaming_manager.get_streaming_chunks(test_audio, chunk_size)
            )

            end_time = time.time()
            processing_time = end_time - start_time

            # Verify data integrity
            reconstructed = b"".join(chunks)
            assert reconstructed == test_audio

            # Calculate metrics
            num_chunks = len(chunks)
            throughput = len(test_audio) / processing_time if processing_time > 0 else 0

            performance_results[chunk_size] = {
                "processing_time": processing_time,
                "num_chunks": num_chunks,
                "throughput_bps": throughput,
                "chunk_efficiency": (
                    len(test_audio) / (num_chunks * chunk_size) if num_chunks > 0 else 0
                ),
            }

        # Verify performance characteristics
        for chunk_size, results in performance_results.items():
            # Processing should be fast
            assert (
                results["processing_time"] < 0.1
            ), f"Chunk size {chunk_size}: Processing too slow"

            # Throughput should be reasonable
            assert (
                results["throughput_bps"] > 100000
            ), f"Chunk size {chunk_size}: Low throughput"

            # Should have reasonable number of chunks
            expected_chunks = (len(test_audio) + chunk_size - 1) // chunk_size
            assert results["num_chunks"] == expected_chunks

    def test_streaming_data_preparation_performance(self, streaming_manager):
        """Test performance of streaming data preparation."""
        audio_sizes = [1024, 10240, 102400, 1024000]  # 1KB to 1MB

        for audio_size in audio_sizes:
            test_audio = b"x" * audio_size

            # Test new synthesis streaming data
            start_time = time.time()
            streaming_data = streaming_manager.prepare_streaming_audio(
                test_audio, is_cached=False
            )
            end_time = time.time()

            preparation_time = end_time - start_time

            # Verify streaming data structure
            assert streaming_data["audio_bytes"] == test_audio
            assert streaming_data["is_cached"] is False
            assert streaming_data["streaming_ready"] is True
            assert "gradio_audio" in streaming_data
            assert "gradio_tuple" in streaming_data

            # Performance should scale reasonably with size
            assert (
                preparation_time < 1.0
            ), f"Audio size {audio_size}: Preparation too slow ({preparation_time:.3f}s)"

            # Test cached audio streaming data
            start_time = time.time()
            cached_data = streaming_manager.create_instant_replay_data(test_audio)
            end_time = time.time()

            cached_preparation_time = end_time - start_time

            # Cached preparation should be faster
            assert (
                cached_preparation_time <= preparation_time
            ), "Cached preparation should be faster"
            assert cached_data["instant_replay"] is True

    def test_concurrent_streaming_operations(self, streaming_manager):
        """Test concurrent streaming operations performance."""
        num_streams = 10
        test_audio = b"concurrent_streaming_test" * 100  # ~2.5KB per stream

        def streaming_worker(stream_id):
            """Worker function for concurrent streaming."""
            try:
                # Prepare streaming data
                streaming_data = streaming_manager.prepare_streaming_audio(
                    test_audio, is_cached=(stream_id % 2 == 0)
                )

                # Start streaming
                success = streaming_manager.start_streaming(streaming_data)

                # Brief processing time
                time.sleep(0.01)

                # Stop streaming
                streaming_manager.stop_streaming()

                return {"stream_id": stream_id, "success": success}

            except Exception as e:
                return {"stream_id": stream_id, "success": False, "error": str(e)}

        # Run concurrent streaming operations
        threads = []
        results = []

        start_time = time.time()

        for i in range(num_streams):
            thread = threading.Thread(
                target=lambda i=i: results.append(streaming_worker(i))
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        end_time = time.time()
        total_time = end_time - start_time

        # Analyze results
        successful_streams = [r for r in results if r.get("success")]
        success_rate = len(successful_streams) / num_streams

        # Should handle concurrent streaming well
        assert (
            success_rate > 0.8
        ), f"Concurrent streaming success rate: {success_rate:.2%}"

        # Should complete within reasonable time
        assert (
            total_time < 5.0
        ), f"Concurrent streaming took too long: {total_time:.2f}s"

    def test_audio_format_conversion_performance(self):
        """Test performance of audio format conversion."""
        audio_sizes = [1024, 10240, 102400]  # 1KB to 100KB
        formats = ["mp3", "wav", "ogg"]

        for audio_size in audio_sizes:
            test_audio = b"format_test_" * (audio_size // 12)  # Approximate size

            for format_type in formats:
                start_time = time.time()

                # Convert to Gradio format
                gradio_uri = AudioFormatConverter.convert_to_gradio_format(
                    test_audio, format_type
                )

                end_time = time.time()
                conversion_time = end_time - start_time

                # Verify conversion
                assert gradio_uri.startswith(f"data:audio/")
                assert "base64," in gradio_uri

                # Performance should be reasonable
                assert (
                    conversion_time < 0.5
                ), f"Format {format_type}, size {audio_size}: Conversion too slow"

                # Test Gradio component data creation
                start_time = time.time()
                component_data = (
                    AudioFormatConverter.create_gradio_audio_component_data(test_audio)
                )
                end_time = time.time()

                component_time = end_time - start_time
                assert component_time < 0.1, "Component data creation too slow"
                assert component_data == (44100, test_audio)


class TestNetworkConditionsSimulation:
    """Test system behavior under network latency and packet loss."""

    @pytest.fixture
    def tts_service(self):
        """Provide TTS service for network testing."""
        config = TTSConfig(api_key="network_test_key")
        return TTSService(config)

    @pytest.mark.asyncio
    async def test_high_latency_conditions(self, tts_service):
        """Test behavior under high network latency."""
        test_text = "High latency test"
        test_audio = b"high_latency_audio_data"

        # Simulate high latency response
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(2.0)  # 2 second delay
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=test_audio)
            return mock_response

        mock_session = AsyncMock()
        mock_session.post = slow_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            start_time = time.time()
            result = await tts_service.synthesize_text(test_text)
            end_time = time.time()

            response_time = end_time - start_time

            # Should handle high latency gracefully
            assert result == test_audio
            assert (
                2.0 <= response_time < 5.0
            )  # Should include the delay but not timeout

    @pytest.mark.asyncio
    async def test_intermittent_connectivity(self, tts_service):
        """Test behavior with intermittent network connectivity."""
        test_text = "Intermittent connectivity test"
        test_audio = b"intermittent_test_audio"

        call_count = 0

        async def intermittent_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: connection error
                raise aiohttp.ClientConnectorError(
                    connection_key=None, os_error=ConnectionError("Network unreachable")
                )
            else:
                # Second call: success
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=test_audio)
                return mock_response

        mock_session = AsyncMock()
        mock_session.post = intermittent_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Should recover from intermittent connectivity
            result = await tts_service.synthesize_text(test_text)
            assert result == test_audio
            assert call_count == 2  # Should have retried

    @pytest.mark.asyncio
    async def test_partial_response_handling(self, tts_service):
        """Test handling of partial/corrupted responses."""
        test_text = "Partial response test"

        # Mock response that fails during read
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read.side_effect = aiohttp.ClientPayloadError("Partial response")

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Should handle partial responses gracefully
            with pytest.raises(TTSNetworkError, match="Network error"):
                await tts_service.synthesize_text(test_text)

            # Error state should be updated
            error_state = tts_service.get_error_state()
            assert error_state["has_error"] is True

    @pytest.mark.asyncio
    async def test_dns_resolution_delays(self, tts_service):
        """Test behavior with DNS resolution delays."""
        test_text = "DNS delay test"

        # Simulate DNS resolution delay
        async def dns_delay_response(*args, **kwargs):
            await asyncio.sleep(1.0)  # Simulate DNS delay
            raise aiohttp.ClientConnectorError(
                connection_key=None, os_error=OSError("Name resolution timeout")
            )

        mock_session = AsyncMock()
        mock_session.post = dns_delay_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            start_time = time.time()

            with pytest.raises(Exception):  # Should eventually fail
                await tts_service.synthesize_text(test_text)

            end_time = time.time()

            # Should have attempted with reasonable timeout
            assert 1.0 <= (end_time - start_time) < 10.0


class TestRecoveryMechanisms:
    """Test recovery mechanisms after temporary service outages."""

    @pytest.fixture
    def recovery_service(self):
        """Provide TTS service for recovery testing."""
        config = TTSConfig(api_key="recovery_test_key")
        return TTSService(config)

    @pytest.mark.asyncio
    async def test_service_outage_recovery(self, recovery_service):
        """Test recovery after temporary service outage."""
        test_text = "Service outage recovery test"
        test_audio = b"recovery_test_audio"

        call_count = 0

        async def outage_simulation(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_response = AsyncMock()

            if call_count <= 3:
                # First 3 calls: service unavailable
                mock_response.status = 503
                mock_response.text = AsyncMock(
                    return_value="Service temporarily unavailable"
                )
            else:
                # 4th call: service recovered
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=test_audio)

            return mock_response

        mock_session = AsyncMock()
        mock_session.post = outage_simulation
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Should recover after outage
            result = await recovery_service.synthesize_text(test_text)
            assert result == test_audio
            assert call_count == 4  # Should have retried through outage

    @pytest.mark.asyncio
    async def test_error_state_recovery(self, recovery_service):
        """Test error state recovery mechanisms."""
        test_text = "Error state recovery test"
        test_audio = b"error_recovery_audio"

        # Force service into error state
        test_error = TTSServerError("Forced error for testing", 500)
        recovery_service.error_handler._update_error_state(test_error)

        # Verify error state
        error_state = recovery_service.get_error_state()
        assert error_state["has_error"] is True

        # Mock successful recovery
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=test_audio)

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Attempt recovery
            recovery_success = await recovery_service.attempt_recovery()
            assert recovery_success is True

            # Error state should be cleared
            error_state = recovery_service.get_error_state()
            assert error_state["has_error"] is False

            # Service should work normally
            result = await recovery_service.synthesize_text(test_text)
            assert result == test_audio

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, recovery_service):
        """Test circuit breaker recovery after failures."""
        test_text = "Circuit breaker recovery test"
        test_audio = b"circuit_recovery_audio"

        # Force circuit breaker to open
        for _ in range(10):
            recovery_service.error_handler.circuit_breaker.record_failure()

        # Verify circuit is open
        circuit_state = recovery_service.get_circuit_breaker_state()
        assert circuit_state["state"] == "open"

        # Wait for cooldown period
        await asyncio.sleep(1.1)  # Slightly longer than cooldown

        # Mock successful responses for recovery
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=test_audio)

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Should transition to half-open and then closed
            result = await recovery_service.synthesize_text(test_text)
            assert result == test_audio

            # Circuit should be in half-open or closed state
            circuit_state = recovery_service.get_circuit_breaker_state()
            assert circuit_state["state"] in ["half_open", "closed"]

    def test_cache_recovery_after_corruption(self):
        """Test cache recovery after data corruption."""
        temp_dir = tempfile.mkdtemp()

        try:
            config = CacheConfig(
                backend="multi-tier", persistent_path=temp_dir, memory_max_size=10
            )

            # Create cache and add data
            cache = MultiTierAudioCache(config)
            test_text = "Cache corruption test"
            test_audio = b"cache_corruption_audio"

            cache.put(test_text, test_audio)

            # Verify data exists
            assert cache.get(test_text) == test_audio

            # Simulate cache corruption by clearing memory cache
            cache.backends["memory"].clear()

            # Should still retrieve from persistent cache
            retrieved = cache.get(test_text)
            assert retrieved == test_audio

            # Memory cache should be warmed
            cache_key = cache._generate_hash(test_text)
            assert cache.backends["memory"].has(cache_key)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestPerformanceOptimization:
    """Test performance optimization validation."""

    @pytest.fixture
    def optimized_service(self):
        """Provide optimized TTS service for performance testing."""
        temp_dir = tempfile.mkdtemp()

        config = TTSConfig(api_key="optimization_test_key")
        cache_config = CacheConfig(
            backend="multi-tier",
            persistent_path=temp_dir,
            memory_max_size=50,
            memory_max_mb=20,
        )

        service = TTSService(config, cache_config)

        yield service

        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, optimized_service):
        """Test cache hit performance optimization."""
        test_text = "Cache hit performance test"
        test_audio = b"cache_hit_audio_data"

        # Pre-populate cache
        optimized_service.cache_audio(test_text, test_audio)

        # Measure cache hit performance
        cache_hit_times = []

        for _ in range(10):
            start_time = time.time()
            result = await optimized_service.synthesize_text(test_text)
            end_time = time.time()

            cache_hit_times.append(end_time - start_time)
            assert result == test_audio

        # Cache hits should be very fast
        avg_cache_hit_time = sum(cache_hit_times) / len(cache_hit_times)
        assert (
            avg_cache_hit_time < 0.01
        ), f"Cache hits too slow: {avg_cache_hit_time:.4f}s"

        # Should be consistent
        max_cache_hit_time = max(cache_hit_times)
        assert (
            max_cache_hit_time < 0.05
        ), f"Inconsistent cache performance: {max_cache_hit_time:.4f}s"

    def test_memory_cache_efficiency(self, optimized_service):
        """Test memory cache efficiency."""
        # Fill cache with various sized entries
        entries = []
        total_size = 0

        for i in range(100):
            text = f"Memory efficiency test {i}"
            audio_size = 1000 + (i * 100)  # Varying sizes
            audio = b"x" * audio_size

            optimized_service.cache_audio(text, audio)
            entries.append((text, audio, audio_size))
            total_size += audio_size

        # Check cache statistics
        cache_stats = optimized_service.get_cache_stats()

        # Memory cache should have evicted entries to stay within limits
        if "backends" in cache_stats and "memory" in cache_stats["backends"]:
            memory_stats = cache_stats["backends"]["memory"]

            # Should respect size limits
            assert memory_stats.get("entry_count", 0) <= 50

            # Should have reasonable memory usage
            memory_size_mb = memory_stats.get("total_size_bytes", 0) / (1024 * 1024)
            assert memory_size_mb <= 20  # Should respect memory limit

    def test_concurrent_cache_performance(self, optimized_service):
        """Test cache performance under concurrent access."""
        num_threads = 20
        operations_per_thread = 50
        test_audio = b"concurrent_cache_perf_test"

        performance_results = []
        lock = threading.Lock()

        def cache_performance_worker(thread_id):
            """Worker that performs cache operations and measures performance."""
            thread_times = []

            for i in range(operations_per_thread):
                key = f"perf_test_{thread_id}_{i}"

                # Cache write
                start_time = time.time()
                optimized_service.cache_audio(key, test_audio)
                write_time = time.time() - start_time

                # Cache read
                start_time = time.time()
                result = optimized_service.get_cached_audio(key)
                read_time = time.time() - start_time

                thread_times.append(
                    {
                        "write_time": write_time,
                        "read_time": read_time,
                        "success": result == test_audio,
                    }
                )

            with lock:
                performance_results.extend(thread_times)

        # Run concurrent cache operations
        threads = []
        start_time = time.time()

        for i in range(num_threads):
            thread = threading.Thread(target=cache_performance_worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        # Analyze performance results
        successful_ops = [r for r in performance_results if r["success"]]

        if successful_ops:
            avg_write_time = sum(r["write_time"] for r in successful_ops) / len(
                successful_ops
            )
            avg_read_time = sum(r["read_time"] for r in successful_ops) / len(
                successful_ops
            )

            # Cache operations should be fast even under concurrency
            assert (
                avg_write_time < 0.01
            ), f"Concurrent cache writes too slow: {avg_write_time:.4f}s"
            assert (
                avg_read_time < 0.005
            ), f"Concurrent cache reads too slow: {avg_read_time:.4f}s"

        # Overall performance should be reasonable
        ops_per_second = len(performance_results) / total_time
        assert (
            ops_per_second > 1000
        ), f"Cache throughput too low: {ops_per_second:.0f} ops/sec"


class TestReliabilityUnderAdverseConditions:
    """Test reliability under adverse conditions."""

    @pytest.fixture
    def reliable_service(self):
        """Provide TTS service configured for reliability testing."""
        config = TTSConfig(api_key="reliability_test_key")
        return TTSService(config)

    @pytest.mark.asyncio
    async def test_sustained_error_conditions(self, reliable_service):
        """Test reliability under sustained error conditions."""
        test_text = "Sustained error test"

        # Simulate sustained errors
        error_count = 0

        async def sustained_error_response(*args, **kwargs):
            nonlocal error_count
            error_count += 1

            mock_response = AsyncMock()

            if error_count <= 20:
                # First 20 calls: various errors
                if error_count % 3 == 0:
                    mock_response.status = 429
                    mock_response.text = AsyncMock(return_value="Rate limit")
                elif error_count % 3 == 1:
                    mock_response.status = 500
                    mock_response.text = AsyncMock(return_value="Server error")
                else:
                    raise aiohttp.ClientConnectorError(
                        connection_key=None, os_error=ConnectionError("Network error")
                    )
            else:
                # Eventually succeed
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=b"sustained_error_recovery")

            return mock_response

        mock_session = AsyncMock()
        mock_session.post = sustained_error_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Test multiple synthesis attempts
        success_count = 0

        with patch("aiohttp.ClientSession", return_value=mock_session):
            for i in range(25):  # Ensure we exceed the error count
                try:
                    result = await reliable_service.synthesize_text(f"{test_text} {i}")
                    success_count += 1
                except Exception:
                    pass  # Expected failures

        # Should eventually achieve some successes despite sustained errors
        assert (
            success_count > 0
        ), "Service should eventually succeed despite sustained errors"

        # Error handling should remain functional
        error_state = reliable_service.get_error_state()
        assert isinstance(error_state, dict)

    def test_resource_exhaustion_handling(self, reliable_service):
        """Test handling of resource exhaustion scenarios."""
        # Simulate memory pressure by creating large cache entries
        large_audio = b"x" * 1024 * 1024  # 1MB per entry

        # Try to exhaust cache memory
        for i in range(100):  # Try to add 100MB
            try:
                text = f"Resource exhaustion test {i}"
                reliable_service.cache_audio(text, large_audio)
            except Exception:
                pass  # Expected to fail at some point

        # Service should remain functional
        cache_stats = reliable_service.get_cache_stats()
        assert isinstance(cache_stats, dict)

        # Should have enforced limits
        if "backends" in cache_stats and "memory" in cache_stats["backends"]:
            memory_stats = cache_stats["backends"]["memory"]
            entry_count = memory_stats.get("entry_count", 0)

            # Should not have unlimited growth
            assert (
                entry_count < 100
            ), f"Cache did not enforce limits: {entry_count} entries"

    @pytest.mark.asyncio
    async def test_rapid_state_changes(self, reliable_service):
        """Test reliability under rapid state changes."""
        test_text = "Rapid state change test"

        # Rapidly change volume settings while performing operations
        async def volume_changer():
            for i in range(50):
                try:
                    volume = 0.1 + (i % 9) * 0.1
                    reliable_service.set_volume(volume)
                    await asyncio.sleep(0.01)
                except Exception:
                    pass

        # Rapidly check error states
        async def state_checker():
            for _ in range(50):
                try:
                    reliable_service.get_error_state()
                    reliable_service.get_circuit_breaker_state()
                    await asyncio.sleep(0.01)
                except Exception:
                    pass

        # Run concurrent rapid state changes
        tasks = [volume_changer(), state_checker()]

        await asyncio.gather(*tasks, return_exceptions=True)

        # Service should remain stable
        final_volume = reliable_service.get_volume()
        assert 0.0 <= final_volume <= 1.0, "Volume should remain in valid range"

        error_state = reliable_service.get_error_state()
        assert isinstance(error_state, dict), "Error state should remain accessible"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
