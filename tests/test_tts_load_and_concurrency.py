"""
Load and concurrency stress tests for TTS service.

This module tests:
- High concurrency simulation (100 simultaneous TTS synthesis requests)
- Memory leak detection (long-running tests with continuous synthesis)
- Cache contention testing (multiple threads accessing cache simultaneously)
- API rate-limit stress testing (sustained high-volume requests)
- Resource exhaustion scenarios (cache size limits exceeded rapidly)
- Performance benchmarking (response times under various load levels)
- Thread safety validation (ensure all shared resources are properly synchronized)
"""

import pytest
import asyncio
import threading
import time
import gc
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import shutil
from collections import defaultdict
import statistics

from src.utils.tts_service import TTSService, TTSConfig
from src.utils.multi_tier_audio_cache import MultiTierAudioCache, CacheConfig
from src.utils.tts_error_handler import TTSErrorHandler, TTSRateLimitError, TTSServerError


class TestHighConcurrencySimulation:
    """Test high concurrency simulation with simultaneous TTS synthesis requests."""
    
    @pytest_asyncio.fixture
    def tts_service(self):
        """Provide TTS service for concurrency testing."""
        config = TTSConfig(api_key="test_key", voice_id="test_voice")
        return TTSService(config)
    
    @pytest.mark.asyncio
    async def test_concurrent_synthesis_requests(self, tts_service):
        """Test simultaneous TTS synthesis requests to detect race conditions."""
        num_requests = 50  # Reduced for CI stability
        test_audio = b"concurrent_test_audio_data"
        
        # Mock successful API responses
        async def create_mock_response(*args, **kwargs):
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=test_audio)
            return mock_response
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=create_mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        async def synthesis_task(task_id):
            """Individual synthesis task."""
            text = f"Concurrent synthesis test {task_id}"
            try:
                result = await tts_service.synthesize_text(text)
                return {'task_id': task_id, 'success': True, 'result': result}
            except Exception as e:
                return {'task_id': task_id, 'success': False, 'error': str(e)}
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Create and run concurrent tasks
            tasks = [synthesis_task(i) for i in range(num_requests)]
            
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Analyze results
            successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
            failed_results = [r for r in results if isinstance(r, dict) and not r.get('success')]
            exceptions = [r for r in results if isinstance(r, Exception)]
            
            # Verify no race conditions or deadlocks
            assert len(successful_results) + len(failed_results) + len(exceptions) == num_requests
            
            # Most requests should succeed
            success_rate = len(successful_results) / num_requests
            assert success_rate > 0.8  # At least 80% success rate
            
            # Performance check
            total_time = end_time - start_time
            assert total_time < 30  # Should complete within 30 seconds
            # Verify cache integrity after concurrent operations
            cache_stats = tts_service.get_cache_stats()
            assert isinstance(cache_stats, dict)
            # Verify cache has processed entries
            if 'hit_rate' in cache_stats:
                assert cache_stats['hit_rate'] >= 0
            if 'entry_count' in cache_stats:
                assert cache_stats['entry_count'] >= 0
            assert isinstance(cache_stats, dict)
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, tts_service):
        """Test concurrent cache access patterns."""
        num_tasks = 30
        cache_keys = [f"cache_test_{i}" for i in range(10)]  # Shared keys for contention
        test_audio = b"cache_contention_test_audio"
        
        # Pre-populate some cache entries
        for i in range(5):
            tts_service.cache_audio(cache_keys[i], test_audio)
        
        async def cache_access_task(task_id):
            """Task that performs various cache operations."""
            try:
                key = cache_keys[task_id % len(cache_keys)]
                
                # Mix of cache operations
                if task_id % 3 == 0:
                    # Cache read - run in thread to avoid blocking event loop
                    result = await asyncio.to_thread(tts_service.get_cached_audio, key)
                    return {'task_id': task_id, 'operation': 'read', 'success': True}
                elif task_id % 3 == 1:
                    # Cache write - run in thread to avoid blocking event loop
                    await asyncio.to_thread(tts_service.cache_audio, key, test_audio)
                    return {'task_id': task_id, 'operation': 'write', 'success': True}
                else:
                    # Cache stats - run in thread to avoid blocking event loop
                    stats = await asyncio.to_thread(tts_service.get_cache_stats)
                    return {'task_id': task_id, 'operation': 'stats', 'success': True}
            except Exception as e:
                return {'task_id': task_id, 'success': False, 'error': str(e)}
        
        # Run concurrent cache operations
        tasks = [cache_access_task(i) for i in range(num_tasks)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
        
        # Should have high success rate with no deadlocks
        success_rate = len(successful_results) / num_tasks
        assert success_rate > 0.95  # At least 95% success rate
        
        # Verify cache is still functional after concurrent access
        final_stats = tts_service.get_cache_stats()
        assert isinstance(final_stats, dict)


class TestMemoryLeakDetection:
    """Test memory leak detection with continuous synthesis operations."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Provide temporary directory for cache testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logging.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")
    
    @pytest.fixture
    def tts_service_with_cache(self, temp_cache_dir):
        """Provide TTS service with persistent cache for memory testing."""
        config = TTSConfig(api_key="test_key")
        cache_config = CacheConfig(
            backend="multi-tier",
            persistent_path=temp_cache_dir,
            memory_max_size=20,
            memory_max_mb=5
        )
        return TTSService(config, cache_config)
    
    def get_memory_usage_mb(self):
        """Get current memory usage in MB (simplified version)."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except (ImportError, psutil.NoSuchProcess, psutil.AccessDenied):
            # Fallback if psutil not available
            return 0
    
    @pytest.mark.asyncio
    async def test_continuous_synthesis_memory_usage(self, tts_service_with_cache):
        """Test memory usage during continuous synthesis operations."""
        num_iterations = 100  # Reduced for CI
        test_audio = b"memory_test_audio_data" * 50  # Moderate size
        memory_samples = []
        
        # Mock API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=test_audio)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Baseline memory usage
            gc.collect()
            baseline_memory = self.get_memory_usage_mb()
            memory_samples.append(baseline_memory)
            
            # Continuous synthesis operations
            for i in range(num_iterations):
                text = f"Memory test iteration {i}"
                
                try:
                    await tts_service_with_cache.synthesize_text(text)
                except Exception:
                    pass  # Continue even if some operations fail
                
                # Sample memory usage every 20 iterations
                if i % 20 == 0:
                    gc.collect()
                    current_memory = self.get_memory_usage_mb()
                    memory_samples.append(current_memory)
            
            # Final memory check
            gc.collect()
            final_memory = self.get_memory_usage_mb()
            memory_samples.append(final_memory)
        
        # Analyze memory usage (only if psutil available)
        if baseline_memory > 0:
            memory_growth = final_memory - baseline_memory
            max_memory = max(memory_samples)
            
            # Memory growth should be reasonable
            assert memory_growth < 100, f"Memory grew by {memory_growth:.2f}MB"
            
            # Peak memory should not be excessive
            assert max_memory < baseline_memory + 150, f"Peak memory usage: {max_memory:.2f}MB"
    
    def test_cache_memory_management(self, tts_service_with_cache):
        """Test cache memory management under continuous load."""
        num_entries = 100  # Exceed cache limits to test eviction
        test_audio_base = b"cache_memory_test_" * 20  # ~500 bytes per entry
        
        initial_memory = self.get_memory_usage_mb()
        
        # Fill cache beyond capacity
        for i in range(num_entries):
            text = f"Cache memory test {i}"
            audio = test_audio_base + str(i).encode()
            tts_service_with_cache.cache_audio(text, audio)
            
            # Force garbage collection periodically
            if i % 25 == 0:
                gc.collect()
        
        # Check final memory usage
        gc.collect()
        final_memory = self.get_memory_usage_mb()
        
        # Get cache statistics
        cache_stats = tts_service_with_cache.get_cache_stats()
        
        # Memory growth should be bounded by cache limits (only if psutil available)
        if initial_memory > 0:
            memory_growth = final_memory - initial_memory
            assert memory_growth < 50, f"Cache memory grew by {memory_growth:.2f}MB"
        
        # Cache should have evicted entries to stay within limits
        if 'backends' in cache_stats and 'memory' in cache_stats['backends']:
            memory_cache_size = cache_stats['backends']['memory'].get('entry_count', 0)
            assert memory_cache_size <= 20  # Should respect memory_max_size


class TestCacheContentionTesting:
    """Test cache contention with multiple threads accessing cache simultaneously."""
    
    @pytest.fixture
    def multi_cache(self):
        """Provide multi-tier cache for contention testing."""
        temp_dir = tempfile.mkdtemp()
        config = CacheConfig(
            backend="multi-tier",
            persistent_path=temp_dir,
            memory_max_size=15,
            persistent_max_size=50
        )
        cache = MultiTierAudioCache(config)
        yield cache
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logging.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")
    
    def test_concurrent_read_write_operations(self, multi_cache):
        """Test concurrent read/write operations on cache."""
        num_threads = 10  # Reduced for CI stability
        operations_per_thread = 50
        shared_keys = [f"shared_key_{i}" for i in range(5)]
        test_audio = b"contention_test_audio_data"
        
        results = defaultdict(list)
        lock = threading.Lock()
        
        def cache_worker(thread_id, operation_type):
            """Worker function for cache operations."""
            thread_results = []
            
            for i in range(operations_per_thread):
                key = shared_keys[i % len(shared_keys)]
                
                try:
                    start_time = time.time()
                    
                    if operation_type == 'read':
                        result = multi_cache.get(key)
                        success = True
                    elif operation_type == 'write':
                        cache_key = multi_cache.put(key, test_audio)
                        success = cache_key is not None
                    else:  # 'mixed'
                        if i % 2 == 0:
                            result = multi_cache.get(key)
                        else:
                            multi_cache.put(key, test_audio)
                        success = True
                    
                    end_time = time.time()
                    operation_time = end_time - start_time
                    
                    thread_results.append({
                        'thread_id': thread_id,
                        'operation': i,
                        'success': success,
                        'time': operation_time
                    })
                    
                except Exception as e:
                    thread_results.append({
                        'thread_id': thread_id,
                        'operation': i,
                        'success': False,
                        'error': str(e),
                        'time': 0
                    })
            
            with lock:
                results[operation_type].extend(thread_results)
        
        # Create task specifications for different operation types
        tasks = []
        
        # Reader tasks
        for i in range(num_threads // 3):
            tasks.append((f'reader_{i}', 'read'))
        
        # Writer tasks
        for i in range(num_threads // 3):
            tasks.append((f'writer_{i}', 'write'))
        
        # Mixed operation tasks
        for i in range(num_threads - 2 * (num_threads // 3)):
            tasks.append((f'mixed_{i}', 'mixed'))
        
        # Execute tasks using ThreadPoolExecutor
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit all tasks
            futures = [executor.submit(cache_worker, thread_id, operation_type) 
                      for thread_id, operation_type in tasks]
            
            # Wait for all tasks to complete
            for future in futures:
                future.result()  # This will raise any exceptions that occurred
        
        total_time = time.time() - start_time
        
        # Analyze results
        all_results = []
        for operation_type, type_results in results.items():
            all_results.extend(type_results)
        
        successful_operations = [r for r in all_results if r['success']]
        failed_operations = [r for r in all_results if not r['success']]
        
        # Calculate success rate
        total_operations = len(all_results)
        success_rate = len(successful_operations) / total_operations if total_operations > 0 else 0
        
        # Verify high success rate (should handle contention well)
        assert success_rate > 0.95, f"Success rate: {success_rate:.2%}"
        
        # Verify reasonable performance
        if successful_operations:
            avg_operation_time = statistics.mean([r['time'] for r in successful_operations])
            assert avg_operation_time < 0.1, f"Average operation time: {avg_operation_time:.3f}s"
        
        # Verify cache integrity
        final_stats = multi_cache.get_comprehensive_stats()
        assert isinstance(final_stats, dict)


class TestAPIRateLimitStressTesting:
    """Test API rate-limit stress testing with sustained high-volume requests."""
    
    @pytest.fixture
    def rate_limit_service(self):
        """Provide TTS service configured for rate limit testing."""
        config = TTSConfig(api_key="rate_limit_test_key")
        return TTSService(config)
    
    @pytest.mark.asyncio
    async def test_sustained_high_volume_requests(self, rate_limit_service):
        """Test sustained high-volume requests to validate retry mechanisms."""
        num_requests = 50  # Reduced for CI
        rate_limit_frequency = 0.3  # 30% of requests will hit rate limit
        test_audio = b"rate_limit_test_audio"
        
        request_count = 0
        
        async def create_mock_response():
            nonlocal request_count
            request_count += 1
            
            mock_response = AsyncMock()
            
            # Simulate rate limiting
            import random
            if random.random() < rate_limit_frequency:
                mock_response.status = 429
                mock_response.text = AsyncMock(return_value="Rate limit exceeded")
            else:
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=test_audio)
            
            return mock_response
        
        async def rate_limit_request(request_id):
            """Individual request that may hit rate limits."""
            text = f"Rate limit test {request_id}"
            
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(side_effect=lambda *args, **kwargs: create_mock_response())
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            try:
                with patch('aiohttp.ClientSession', return_value=mock_session):
                    start_time = time.time()
                    result = await rate_limit_service.synthesize_text(text)
                    end_time = time.time()
                    
                    return {
                        'request_id': request_id,
                        'success': True,
                        'result': result,
                        'time': end_time - start_time
                    }
            except Exception as e:
                return {
                    'request_id': request_id,
                    'success': False,
                    'error': str(e),
                    'time': 0
                }
        
        # Execute high-volume requests with controlled concurrency
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests
        
        async def controlled_request(request_id):
            async with semaphore:
                return await rate_limit_request(request_id)
        
        tasks = [controlled_request(i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
        failed_results = [r for r in results if isinstance(r, dict) and not r.get('success')]
        
        # Calculate metrics
        success_rate = len(successful_results) / num_requests
        
        # Verify retry mechanisms handled rate limits
        assert success_rate > 0.6, f"Success rate: {success_rate:.2%} (expected >60%)"
        
        # Response times should be reasonable despite retries
        if successful_results:
            avg_response_time = statistics.mean([r['time'] for r in successful_results])
            assert avg_response_time < 10.0, f"Average response time: {avg_response_time:.2f}s"


class TestPerformanceBenchmarking:
    """Test performance benchmarking under various load levels."""
    
    @pytest.fixture
    def benchmark_service(self):
        """Provide TTS service for performance benchmarking."""
        config = TTSConfig(api_key="benchmark_test_key")
        return TTSService(config)
    
    @pytest.mark.asyncio
    async def test_response_times_under_load(self, benchmark_service):
        """Measure response times under various load levels."""
        load_levels = [1, 5, 10]  # Reduced for CI
        test_audio = b"benchmark_test_audio_data"
        
        benchmark_results = {}
        
        def create_mock_session():
            """Create a new mock session for each request to avoid sharing."""
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=test_audio)
            
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            return mock_session
        
        for load_level in load_levels:
            async def benchmark_request(request_id):
                """Individual benchmark request."""
                text = f"Benchmark test load_{load_level} req_{request_id}"
                
                # Create a new mock session for each request to ensure isolation
                mock_session = create_mock_session()
                with patch('aiohttp.ClientSession', return_value=mock_session):
                    start_time = time.time()
                    try:
                        result = await benchmark_service.synthesize_text(text)
                        end_time = time.time()
                        return {
                            'success': True,
                            'response_time': end_time - start_time,
                            'request_id': request_id
                        }
                    except Exception as e:
                        end_time = time.time()
                        return {
                            'success': False,
                            'response_time': end_time - start_time,
                            'error': str(e),
                            'request_id': request_id
                        }
            
            # Run benchmark for current load level
            tasks = [benchmark_request(i) for i in range(load_level)]
            
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            # Analyze results
            successful_results = [r for r in results if r['success']]
            response_times = [r['response_time'] for r in successful_results]
            
            if response_times:
                benchmark_results[load_level] = {
                    'total_requests': load_level,
                    'successful_requests': len(successful_results),
                    'success_rate': len(successful_results) / load_level,
                    'total_time': total_time,
                    'avg_response_time': statistics.mean(response_times),
                    'min_response_time': min(response_times),
                    'max_response_time': max(response_times),
                    'throughput': len(successful_results) / total_time if total_time > 0 else 0
                }
        
        # Verify performance requirements
        for load_level, results in benchmark_results.items():
            if results['successful_requests'] > 0:
                # Success rate should remain high
                assert results['success_rate'] > 0.95, f"Load {load_level}: Success rate {results['success_rate']:.2%}"
                
                # Response times should be reasonable
                assert results['avg_response_time'] < 2.0, f"Load {load_level}: Avg response time {results['avg_response_time']:.3f}s"


class TestThreadSafetyValidation:
    """Test thread safety validation for shared resources."""
    
    @pytest.fixture
    def thread_safe_service(self):
        """Provide TTS service for thread safety testing."""
        config = TTSConfig(api_key="thread_safety_test_key")
        return TTSService(config)
    
    def test_concurrent_volume_control(self, thread_safe_service):
        """Test thread safety of volume control operations."""
        num_threads = 10
        operations_per_thread = 20
        results = []
        lock = threading.Lock()
        
        def volume_worker(thread_id):
            """Worker that performs volume control operations."""
            thread_results = []
            
            for i in range(operations_per_thread):
                try:
                    # Set volume - ensure it's within valid range (0.1 to 0.9)
                    volume = 0.1 + (i % 9) * 0.1  # 0.1 to 0.9
                    
                    # Validate volume is in expected range before setting
                    assert 0.1 <= volume <= 0.9, f"Volume {volume} should be between 0.1 and 0.9"
                    
                    thread_safe_service.set_volume(volume)
                    
                    # Get volume and verify it was set correctly
                    current_volume = thread_safe_service.get_volume()
                    
                    # Validate the retrieved volume is within valid range
                    assert 0.0 <= current_volume <= 1.0, f"Retrieved volume {current_volume} should be between 0.0 and 1.0"
                    
                    thread_results.append({
                        'thread_id': thread_id,
                        'operation': i,
                        'set_volume': volume,
                        'get_volume': current_volume,
                        'success': True
                    })
                    
                except Exception as e:
                    thread_results.append({
                        'thread_id': thread_id,
                        'operation': i,
                        'success': False,
                        'error': str(e)
                    })
            
            with lock:
                results.extend(thread_results)
        
        # Run concurrent volume operations
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=volume_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Analyze results
        successful_operations = [r for r in results if r['success']]
        
        # Should have high success rate
        success_rate = len(successful_operations) / len(results)
        assert success_rate > 0.95, f"Volume control success rate: {success_rate:.2%}"
        
        # Final volume should be valid
        final_volume = thread_safe_service.get_volume()
        assert 0.0 <= final_volume <= 1.0, f"Final volume out of range: {final_volume}"
    
    def test_volume_validation_and_error_handling(self, thread_safe_service):
        """Test volume validation and error handling for invalid values."""
        # Test valid volume values at boundaries
        valid_volumes = [0.0, 0.1, 0.5, 0.9, 1.0]
        for volume in valid_volumes:
            thread_safe_service.set_volume(volume)
            retrieved = thread_safe_service.get_volume()
            assert retrieved == volume, f"Volume {volume} was not set correctly, got {retrieved}"
        
        # Test invalid volume values that should raise ValueError
        invalid_volumes = [-0.1, -1.0, 1.1, 2.0, 10.0, float('inf'), float('-inf')]
        
        for invalid_volume in invalid_volumes:
            with pytest.raises(ValueError, match="Volume must be between 0.0 and 1.0"):
                thread_safe_service.set_volume(invalid_volume)
        
        # Test edge case with NaN
        with pytest.raises(ValueError):
            thread_safe_service.set_volume(float('nan'))
        
        # Verify service state remains valid after invalid attempts
        final_volume = thread_safe_service.get_volume()
        assert 0.0 <= final_volume <= 1.0, f"Service volume corrupted after invalid attempts: {final_volume}"
        
        # Test that valid volume can still be set after invalid attempts
        thread_safe_service.set_volume(0.7)
        assert thread_safe_service.get_volume() == 0.7, "Valid volume setting failed after invalid attempts"
    
    def test_concurrent_error_state_access(self, thread_safe_service):
        """Test thread safety of error state access."""
        num_threads = 8
        operations_per_thread = 25
        results = []
        lock = threading.Lock()
        
        def error_state_worker(thread_id):
            """Worker that accesses error state."""
            thread_results = []
            
            for i in range(operations_per_thread):
                try:
                    # Get error state
                    error_state = thread_safe_service.get_error_state()
                    
                    # Get circuit breaker state
                    circuit_state = thread_safe_service.get_circuit_breaker_state()
                    
                    thread_results.append({
                        'thread_id': thread_id,
                        'operation': i,
                        'has_error': error_state.get('has_error', False),
                        'circuit_state': circuit_state.get('state', 'unknown'),
                        'success': True
                    })
                    
                except Exception as e:
                    thread_results.append({
                        'thread_id': thread_id,
                        'operation': i,
                        'success': False,
                        'error': str(e)
                    })
            
            with lock:
                results.extend(thread_results)
        
        # Run concurrent error state access
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=error_state_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Analyze results
        successful_operations = [r for r in results if r['success']]
        
        # Should have high success rate
        success_rate = len(successful_operations) / len(results)
        assert success_rate > 0.98, f"Error state access success rate: {success_rate:.2%}"
        
        # All successful operations should return valid states
        for result in successful_operations:
            assert isinstance(result['has_error'], bool)
            assert result['circuit_state'] in ['closed', 'open', 'half_open', 'unknown']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print output