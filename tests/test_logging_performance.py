"""
Performance tests for logging optimization.

This test suite demonstrates the performance improvements achieved by the optimized logging system.
"""

import logging
import os
import time
from unittest.mock import patch

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.optimized_logging import (
    PerformanceOptimizedLogger,
    OptimizedURLMetadataLogger,
    log_validation_optimized,
    log_upload_optimized,
    configure_optimized_logging,
)
from utils.url_metadata_logger import URLMetadataLogger, log_validation, log_upload


class TestLoggingPerformance:
    """Test performance improvements of optimized logging."""

    def setup_method(self):
        """Setup test environment."""
        # Clear any existing environment variables
        for key in ["LOG_LEVEL", "CONSOLE_LOG_LEVEL", "ENVIRONMENT"]:
            if key in os.environ:
                del os.environ[key]

    def teardown_method(self):
        """Cleanup after tests."""
        # Reset logging configuration
        configure_optimized_logging()

    def expensive_operation(self, value: int) -> str:
        """Simulate an expensive operation for logging."""
        # Simulate some expensive string processing
        result = ""
        for i in range(100):
            result += f"processing_{value}_{i}_"
        return result[:50]  # Truncate to simulate real work

    @pytest.mark.performance
    def test_debug_logging_performance_old_vs_new(self):
        """Compare performance of old vs new debug logging when debug is disabled."""
        
        # Setup old logger with WARNING level (debug disabled)
        old_logger = logging.getLogger("test_old")
        old_logger.setLevel(logging.WARNING)
        
        # Setup new logger with WARNING level (debug disabled)
        new_logger = PerformanceOptimizedLogger("test_new", "WARNING")
        
        iterations = 1000
        
        # Test old logging performance (always formats strings)
        start_time = time.time()
        for i in range(iterations):
            old_logger.debug(f"Processing item {i}: {self.expensive_operation(i)}")
        old_time = time.time() - start_time
        
        # Test new logging performance (conditional formatting)
        start_time = time.time()
        for i in range(iterations):
            new_logger.debug(f"Processing item {i}: {self.expensive_operation(i)}")
        new_time = time.time() - start_time
        
        print(f"\nOld logging time: {old_time:.3f}s")
        print(f"New logging time: {new_time:.3f}s")
        print(f"Performance improvement: {((old_time - new_time) / old_time * 100):.1f}%")
        
        # New logging should be significantly faster when debug is disabled
        assert new_time < old_time * 0.5, f"Expected at least 50% improvement, got {new_time:.3f}s vs {old_time:.3f}s"

    @pytest.mark.performance
    def test_lazy_logging_performance(self):
        """Test lazy logging performance benefits."""
        
        logger = PerformanceOptimizedLogger("test_lazy", "WARNING")  # Debug disabled
        iterations = 1000
        
        # Test regular debug (still formats when disabled)
        start_time = time.time()
        for i in range(iterations):
            logger.debug(f"Regular: {self.expensive_operation(i)}")
        regular_time = time.time() - start_time
        
        # Test lazy debug (skips formatting when disabled)
        start_time = time.time()
        for i in range(iterations):
            logger.debug_lazy(lambda i=i: f"Lazy: {self.expensive_operation(i)}")
        lazy_time = time.time() - start_time
        
        print(f"\nRegular debug time: {regular_time:.3f}s")
        print(f"Lazy debug time: {lazy_time:.3f}s")
        print(f"Lazy improvement: {((regular_time - lazy_time) / regular_time * 100):.1f}%")
        
        # Lazy logging should be much faster
        assert lazy_time < regular_time * 0.3, f"Expected lazy logging to be 70% faster"

    @pytest.mark.performance
    def test_conditional_logging_performance(self):
        """Test conditional logging performance."""
        
        logger = PerformanceOptimizedLogger("test_conditional", "WARNING")
        iterations = 1000
        
        # Test without condition check
        start_time = time.time()
        for i in range(iterations):
            expensive_result = self.expensive_operation(i)
            logger.debug(f"Without condition: {expensive_result}")
        without_condition_time = time.time() - start_time
        
        # Test with condition check
        start_time = time.time()
        for i in range(iterations):
            if logger.is_debug_enabled():
                expensive_result = self.expensive_operation(i)
                logger.debug(f"With condition: {expensive_result}")
        with_condition_time = time.time() - start_time
        
        print(f"\nWithout condition time: {without_condition_time:.3f}s")
        print(f"With condition time: {with_condition_time:.3f}s")
        print(f"Conditional improvement: {((without_condition_time - with_condition_time) / without_condition_time * 100):.1f}%")
        
        # Conditional logging should be much faster
        assert with_condition_time < without_condition_time * 0.2, "Expected conditional logging to be 80% faster"

    @pytest.mark.performance
    def test_url_metadata_logging_performance(self):
        """Test URL metadata logging performance improvements."""
        
        # Setup environment for minimal logging
        os.environ["LOG_LEVEL"] = "WARNING"
        os.environ["ENVIRONMENT"] = "production"
        
        # Create old and new loggers
        old_logger = URLMetadataLogger(log_dir="logs/test_old")
        new_logger = OptimizedURLMetadataLogger("WARNING")
        
        iterations = 500
        test_url = "https://example.com/very/long/url/path/that/might/need/truncation"
        
        # Test old URL validation logging
        start_time = time.time()
        for i in range(iterations):
            log_validation(test_url, True, "url_format", details={"test": f"data_{i}"})
        old_time = time.time() - start_time
        
        # Test new URL validation logging
        start_time = time.time()
        for i in range(iterations):
            log_validation_optimized(test_url, True, "url_format", details={"test": f"data_{i}"})
        new_time = time.time() - start_time
        
        print(f"\nOld URL logging time: {old_time:.3f}s")
        print(f"New URL logging time: {new_time:.3f}s")
        print(f"URL logging improvement: {((old_time - new_time) / old_time * 100):.1f}%")
        
        # New logging should be faster
        assert new_time < old_time * 0.8, "Expected at least 20% improvement in URL logging"

    @pytest.mark.performance
    def test_memory_usage_optimization(self):
        """Test memory usage improvements."""
        import gc
        import sys
        
        # Force garbage collection
        gc.collect()
        
        logger = PerformanceOptimizedLogger("test_memory", "WARNING")
        iterations = 1000
        
        # Measure memory before
        initial_objects = len(gc.get_objects())
        
        # Perform logging operations that should not create objects when disabled
        for i in range(iterations):
            logger.debug(f"Memory test {i}: {self.expensive_operation(i)}")
            logger.info(f"Info test {i}: {self.expensive_operation(i)}")
        
        # Force garbage collection again
        gc.collect()
        
        # Measure memory after
        final_objects = len(gc.get_objects())
        objects_created = final_objects - initial_objects
        
        print(f"\nObjects created during {iterations} disabled log calls: {objects_created}")
        
        # Should create minimal objects when logging is disabled
        assert objects_created < iterations * 0.1, f"Too many objects created: {objects_created}"

    @pytest.mark.performance 
    def test_production_environment_optimization(self):
        """Test that production environment settings provide optimal performance."""
        
        # Set production environment
        os.environ["ENVIRONMENT"] = "production"
        os.environ["LOG_LEVEL"] = "WARNING"
        
        # Reconfigure logging
        configure_optimized_logging()
        
        logger = PerformanceOptimizedLogger("test_production", "WARNING")
        
        iterations = 1000
        
        # All debug and info logging should be extremely fast in production
        start_time = time.time()
        for i in range(iterations):
            logger.debug(f"Debug in production: {self.expensive_operation(i)}")
            logger.info(f"Info in production: {self.expensive_operation(i)}")
        production_time = time.time() - start_time
        
        print(f"\nProduction logging time for {iterations} calls: {production_time:.3f}s")
        print(f"Average time per log call: {(production_time / iterations * 1000):.3f}ms")
        
        # Should be very fast (less than 1ms per call on average)
        assert production_time < iterations * 0.001, f"Production logging too slow: {production_time:.3f}s"

    def test_third_party_logging_suppression(self):
        """Test that third-party library logging is properly suppressed."""
        
        # Configure optimized logging
        configure_optimized_logging()
        
        # Check that third-party loggers are set to WARNING level
        assert logging.getLogger("requests").level >= logging.WARNING
        assert logging.getLogger("urllib3").level >= logging.WARNING
        assert logging.getLogger("pinecone").level >= logging.WARNING
        
        print("\n✅ Third-party logging properly suppressed")

    @pytest.mark.performance
    def test_log_truncation_performance(self):
        """Test performance of URL and query truncation."""
        
        logger = OptimizedURLMetadataLogger("INFO")
        
        # Create very long URL and query
        long_url = "https://example.com/" + "very_long_path/" * 100
        long_query = "SELECT * FROM table WHERE " + "condition AND " * 50
        
        iterations = 1000
        
        # Test URL truncation performance
        start_time = time.time()
        for i in range(iterations):
            logger.log_validation(long_url, True, "format_check")
        url_time = time.time() - start_time
        
        # Test query truncation performance
        start_time = time.time()
        for i in range(iterations):
            logger.log_retrieval(long_query, 10)
        query_time = time.time() - start_time
        
        print(f"\nURL truncation time for {iterations} calls: {url_time:.3f}s")
        print(f"Query truncation time for {iterations} calls: {query_time:.3f}s")
        
        # Truncation should be efficient
        assert url_time < 1.0, "URL truncation taking too long"
        assert query_time < 1.0, "Query truncation taking too long"


@pytest.mark.performance
class TestLoggingMemoryLeaks:
    """Test for memory leaks in logging system."""
    
    def test_no_memory_leaks_in_disabled_logging(self):
        """Ensure disabled logging doesn't create memory leaks."""
        import gc
        import weakref
        
        logger = PerformanceOptimizedLogger("test_leaks", "ERROR")  # Most logging disabled
        
        # Create some objects that might leak
        test_objects = []
        weak_refs = []
        
        for i in range(100):
            obj = {"data": f"test_data_{i}" * 10}
            test_objects.append(obj)
            weak_refs.append(weakref.ref(obj))
            
            # Log with the object (should not retain reference)
            logger.debug(f"Object {i}: {obj}")
            logger.info(f"Object {i}: {obj}")
        
        # Clear strong references
        test_objects.clear()
        gc.collect()
        
        # Check that objects were garbage collected
        alive_objects = sum(1 for ref in weak_refs if ref() is not None)
        
        print(f"\nObjects still alive after logging: {alive_objects}/100")
        
        # Should not retain references to logged objects
        assert alive_objects == 0, f"Memory leak detected: {alive_objects} objects still referenced"


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-m", "performance", "--tb=short"])
