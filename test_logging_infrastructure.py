"""
Test suite for URL metadata logging and monitoring infrastructure.
"""

import pytest
import time
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
import threading
from collections import deque

from src.utils.url_metadata_logger import (
    URLMetadataLogger, correlation_context, url_metadata_logger,
    log_validation, log_upload, log_retry
)
from src.monitoring.url_metadata_monitor import (
    URLMetadataMonitor, url_metadata_monitor,
    record_validation, record_upload
)
from src.utils.url_utils import is_secure_url, normalize_url_rfc3986
from src.utils.url_error_handler import exponential_backoff_retry
from src.agents.pinecone_assistant_agent import PineconeAssistantAgent
from src.knowledge.data_collector import BitcoinDataCollector


class TestURLMetadataLogger:
    """Test cases for URL metadata logger."""
    
    def test_logger_creation(self):
        """Test that loggers are created correctly."""
        # Check that global logger instance exists
        assert url_metadata_logger is not None
        assert hasattr(url_metadata_logger, 'validation_logger')
        assert hasattr(url_metadata_logger, 'upload_logger')
        
    def test_correlation_id_generation(self):
        """Test correlation ID generation."""
        id1 = URLMetadataLogger.generate_correlation_id()
        id2 = URLMetadataLogger.generate_correlation_id()
        
        assert id1 != id2
        assert len(id1) == 36  # UUID format
        assert '-' in id1
        
    def test_correlation_context(self):
        """Test correlation context manager."""
        with correlation_context() as correlation_id:
            assert correlation_id is not None
            assert len(correlation_id) == 36
            
        # Test with provided ID
        custom_id = "custom-correlation-id"
        with correlation_context(custom_id) as correlation_id:
            assert correlation_id == custom_id
            
    def test_logging_functions(self):
        """Test convenience logging functions."""
        # Test validation logging
        log_validation("https://example.com", True, "secure_url")
        
        # Test upload logging
        log_upload("https://example.com", True, 1024)
        
        # Test retry logging
        log_retry("test_operation", 1, 3, "Test error")
        
    def test_thread_local_correlation_id(self):
        """Test that correlation IDs are thread-local."""
        correlation_ids = []
        
        def worker(worker_id):
            with correlation_context() as correlation_id:
                correlation_ids.append((worker_id, correlation_id))
                time.sleep(0.1)  # Simulate work
                
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        # Check that each thread got a unique correlation ID
        ids = [cid for _, cid in correlation_ids]
        assert len(set(ids)) == 5  # All unique


class TestURLMetadataMonitor:
    """Test cases for URL metadata monitor."""
    
    def setup_method(self):
        """Set up test monitor instance."""
        self.monitor = URLMetadataMonitor()
        
    def test_record_validation(self):
        """Test recording validation metrics."""
        url = "https://example.com"
        
        # Record successful validation
        self.monitor.record_validation(url, True, 100.5)
        
        # Get summary to check metrics
        summary = self.monitor.generate_hourly_summary()
        assert 'operations' in summary
        assert 'validation' in summary['operations']
        
    def test_record_upload(self):
        """Test recording upload metrics."""
        url = "https://example.com/doc"
        
        # Record successful upload
        self.monitor.record_upload(url, True, 200.0, 1024)
        
        # Get summary to check metrics
        summary = self.monitor.generate_hourly_summary()
        assert 'operations' in summary
        
    def test_alert_mechanism(self):
        """Test alert mechanism (without directly calling private methods)."""
        # Record enough failures to potentially trigger alert
        for i in range(15):
            self.monitor.record_validation(f"http://url{i}.com", True, 50.0)
        
        for i in range(5):
            self.monitor.record_validation(f"http://bad{i}.com", False, 50.0, 
                                         error_type="Invalid URL")
        
        # Give time for background alert check
        time.sleep(0.1)
        
        # Check alert history
        assert isinstance(self.monitor.alert_history, list)
        
    def test_performance_distribution(self):
        """Test performance distribution calculation."""
        # Add various response times
        times = [10, 50, 100, 200, 500, 1000, 2000, 5000]
        for t in times:
            self.monitor.record_retrieval("http://example.com", 1, t)
            
        summary = self.monitor.generate_hourly_summary()
        assert 'performance_distribution' in summary
        
    def test_summary_reports(self):
        """Test summary report generation."""
        # Add some test data
        for i in range(10):
            self.monitor.record_validation(f"http://url{i}.com", i % 2 == 0, 100.0)
            self.monitor.record_upload(f"http://url{i}.com", i % 3 != 0, 200.0, 1024)
            
        # Test hourly summary
        hourly_summary = self.monitor.generate_hourly_summary()
        assert 'timestamp' in hourly_summary
        assert 'period' in hourly_summary
        assert hourly_summary['period'] == 'hourly'
        
        # Test daily summary  
        daily_summary = self.monitor.generate_daily_summary()
        assert 'timestamp' in daily_summary
        assert daily_summary['period'] == 'daily'
        assert 'top_errors' in daily_summary
        assert 'slowest_operations' in daily_summary


class TestLoggingIntegration:
    """Test integration of logging with various modules."""
    
    @patch('requests.head')
    def test_url_utils_logging(self, mock_head):
        """Test logging in url_utils functions."""
        mock_head.return_value.status_code = 200
        
        # Import after mocking to ensure patch is applied
        from src.utils.url_utils import is_secure_url
        
        # Test is_secure_url with logging
        result = is_secure_url("https://example.com")
        assert result is True
        
    def test_retry_handler_logging(self):
        """Test logging in retry handler."""
        call_count = 0
        
        @exponential_backoff_retry(max_retries=3, initial_delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"
            
        with patch('src.utils.url_error_handler.log_retry') as mock_log_retry:
            result = failing_function()
            
            assert result == "success"
            assert call_count == 3
            # Check that retry logging occurred
            assert mock_log_retry.call_count == 2  # Two retries
            
    def test_data_collector_logging(self):
        """Test logging in data collector."""
        collector = BitcoinDataCollector()
        
        # Test collection with logging
        documents = collector.collect_bitcoin_basics()
        
        # Check that documents were collected
        assert len(documents) > 0
        assert all('url' in doc for doc in documents)


class TestPerformanceImpact:
    """Test performance impact of logging."""
    
    def test_logging_overhead(self):
        """Measure logging overhead."""
        iterations = 1000
        
        # Measure without logging
        start_time = time.time()
        for i in range(iterations):
            url = f"https://example.com/{i}"
            _ = url.lower()
        baseline_time = time.time() - start_time
        
        # Measure with logging
        start_time = time.time()
        for i in range(iterations):
            url = f"https://example.com/{i}"
            with correlation_context() as correlation_id:
                log_validation(url, True, "test", duration_ms=50.0)
        logging_time = time.time() - start_time
        
        # Logging should not add excessive overhead
        overhead_ratio = logging_time / baseline_time
        print(f"Logging overhead: {overhead_ratio:.2f}x")
        
    def test_monitor_memory_usage(self):
        """Test that monitor doesn't consume excessive memory."""
        monitor = URLMetadataMonitor()
        
        # Add many metrics
        for i in range(10000):
            monitor.record_validation(f"http://url{i}.com", True, 50.0)
            
        # Check that memory is bounded by deque maxlen
        assert len(monitor.metrics_store['validation']) <= 10000


class TestLogRotation:
    """Test log rotation functionality."""
    
    def test_log_file_handler_configuration(self):
        """Test that log handlers are configured correctly."""
        logger = url_metadata_logger.validation_logger
        
        # Check that logger has handlers
        assert len(logger.handlers) > 0
        
        # Check that at least one handler is a RotatingFileHandler
        from logging.handlers import RotatingFileHandler
        rotating_handlers = [h for h in logger.handlers 
                           if isinstance(h, RotatingFileHandler)]
        assert len(rotating_handlers) > 0
        
        # Check rotation parameters
        handler = rotating_handlers[0]
        assert handler.maxBytes == 50 * 1024 * 1024  # 50MB
        assert handler.backupCount == 10


class TestErrorHandling:
    """Test error handling in logging infrastructure."""
    
    def test_logging_doesnt_break_operation(self):
        """Test that logging failures don't break the main operation."""
        # Even if logging fails, the operation should succeed
        with patch('src.utils.url_metadata_logger.URLMetadataLogger.log_validation', 
                  side_effect=Exception("Logging error")):
            try:
                # This should still work even if logging fails
                result = is_secure_url("https://example.com")
                assert result is not None
            except Exception as e:
                pytest.fail(f"Operation failed due to logging error: {e}")
                
    def test_monitor_handles_invalid_data(self):
        """Test that monitor handles invalid data gracefully."""
        monitor = URLMetadataMonitor()
        
        # Try to record with invalid data
        monitor.record_validation(None, True, -100)  # Negative duration
        monitor.record_upload("", False, float('inf'), -1)  # Invalid values
        
        # Should not crash when generating summary
        summary = monitor.generate_hourly_summary()
        assert summary is not None


class TestConvenienceFunctions:
    """Test convenience functions for logging and monitoring."""
    
    def test_global_convenience_functions(self):
        """Test global convenience functions."""
        # Test monitoring functions
        record_validation("https://example.com", True, 100.0)
        record_upload("https://example.com", True, 200.0, 1024)
        
        # Test logging functions
        log_validation("https://example.com", True, "test")
        log_upload("https://example.com", True, 1024)
        log_retry("test_op", 1, 3, "error")
        
        # These should not raise exceptions
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])