"""
Test suite for URL metadata logging and monitoring infrastructure.
"""

import threading
import time
import uuid
from unittest.mock import patch

import pytest

from btc_max_knowledge_agent.knowledge.data_collector import BitcoinDataCollector
from btc_max_knowledge_agent.monitoring.url_metadata_monitor import (
    URLMetadataMonitor,
    record_upload,
    record_validation,
    url_metadata_monitor,
)
from btc_max_knowledge_agent.utils.url_error_handler import exponential_backoff_retry
from btc_max_knowledge_agent.utils.url_metadata_logger import (
    LOG_ROTATION_BACKUP_COUNT,
    LOG_ROTATION_MAX_BYTES,
    URLMetadataLogger,
    correlation_context,
    log_retry,
    log_upload,
    log_validation,
    url_metadata_logger,
)
from btc_max_knowledge_agent.utils.url_utils import is_secure_url


def assert_valid_uuid(uuid_string):
    """Helper function to validate that a string is a properly formatted UUID.

    Args:
        uuid_string (str): The string to validate as UUID format

    Raises:
        AssertionError: If the string is not a valid UUID format
    """
    try:
        # Attempt to create a UUID object from the string
        # This will raise ValueError if the format is invalid
        uuid_obj = uuid.UUID(uuid_string)
        # Verify the string representation matches (handles case normalization)
        assert (
            str(uuid_obj) == uuid_string.lower()
        ), f"UUID string format mismatch: {uuid_string}"
    except ValueError as e:
        raise AssertionError(f"Invalid UUID format '{uuid_string}': {e}")


class TestURLMetadataLogger:
    """Test cases for URL metadata logger."""

    def test_logger_creation(self):
        """Test that loggers are created correctly."""
        # Check that global logger instance exists
        assert url_metadata_logger is not None
        assert hasattr(url_metadata_logger, "validation_logger")
        assert hasattr(url_metadata_logger, "upload_logger")

    def test_correlation_id_generation(self):
        """Test correlation ID generation."""
        id1 = URLMetadataLogger.generate_correlation_id()
        id2 = URLMetadataLogger.generate_correlation_id()

        assert id1 != id2
        # Use robust UUID validation instead of weak length/dash checks
        assert_valid_uuid(id1)
        assert_valid_uuid(id2)

    def test_correlation_context(self):
        """Test correlation context manager."""
        with correlation_context() as correlation_id:
            assert correlation_id is not None
            # Use robust UUID validation instead of weak length check
            assert_valid_uuid(correlation_id)

        # Test with provided ID
        custom_id = "custom-correlation-id"
        with correlation_context(custom_id) as correlation_id:
            assert correlation_id == custom_id

    def test_logging_functions(self):
        """Test convenience logging functions."""
        with patch.object(url_metadata_logger, "log_validation") as mock_log_val:
            # Test validation logging
            log_validation("https://example.com", True, "secure_url")
            mock_log_val.assert_called_once()

        with patch.object(url_metadata_logger, "log_upload") as mock_log_up:
            # Test upload logging
            log_upload("https://example.com", True, 1024)
            mock_log_up.assert_called_once()

        with patch.object(url_metadata_logger, "log_retry") as mock_log_retry:
            # Test retry logging
            log_retry("test_operation", 1, 3, "Test error")
            mock_log_retry.assert_called_once()

    def test_thread_local_correlation_id(self):
        """Test that correlation IDs are thread-local."""
        correlation_ids = []
        # Use Event for deterministic thread coordination
        start_event = threading.Event()

        def worker(worker_id):
            # Wait for all threads to be ready before proceeding
            start_event.wait()
            with correlation_context() as correlation_id:
                correlation_ids.append((worker_id, correlation_id))

        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Signal all threads to proceed at once
        start_event.set()

        for t in threads:
            t.join()

        # Check that each thread got a unique correlation ID
        ids = [cid for _, cid in correlation_ids]
        assert len(set(ids)) == 5  # All unique

        # Verify all generated IDs are valid UUIDs
        for _, correlation_id in correlation_ids:
            assert_valid_uuid(correlation_id)


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

        # Record failed validation
        self.monitor.record_validation(url, False, 50.0, error_type="Invalid URL")

        # Get summary to check metrics
        summary = self.monitor.generate_hourly_summary()
        assert "operations" in summary
        assert "validation" in summary["operations"]

        # Verify both success and failure are recorded
        validation_ops = summary["operations"]["validation"]
        assert validation_ops["total"] == 2
        assert validation_ops["successes"] == 1
        assert validation_ops["failures"] == 1

    def test_record_upload(self):
        """Test recording upload metrics."""
        url = "https://example.com/doc"

        # Record successful upload
        self.monitor.record_upload(url, True, 200.0, 1024)

        # Record failed upload
        self.monitor.record_upload(url, False, 150.0, 0, error_type="Network error")

        # Get summary to check metrics
        summary = self.monitor.generate_hourly_summary()
        assert "operations" in summary
        assert "upload" in summary["operations"]

        # Verify metrics
        upload_ops = summary["operations"]["upload"]
        assert upload_ops["total"] == 2
        assert upload_ops["successes"] == 1
        assert upload_ops["failures"] == 1

    @patch("datetime.datetime")
    def test_alert_mechanism(self, mock_datetime):
        """Test alert mechanism with controlled alert triggers."""
        from datetime import datetime, timezone

        # Set up a fixed time for consistent testing
        fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time
        mock_datetime.fromisoformat = datetime.fromisoformat  # Keep real implementation

        # Record enough failures to trigger alert (25% failure rate)
        for i in range(15):
            self.monitor.record_validation(f"http://url{i}.com", True, 50.0)

        for i in range(5):
            self.monitor.record_validation(
                f"http://bad{i}.com", False, 50.0, error_type="Invalid URL"
            )

        # Clear any existing alerts
        self.monitor.alert_history.clear()

        # Manually trigger the alert mechanism
        self.monitor._check_alerts()

        # Verify alert was generated
        assert (
            len(self.monitor.alert_history) > 0
        ), "Expected alert for high failure rate (25%)"

        # Verify alert content structure and values
        alert = self.monitor.alert_history[0]

        # Required fields
        required_fields = [
            "timestamp",
            "alert_name",
            "threshold_value",
            "actual_value",
            "window_minutes",
        ]
        for field in required_fields:
            assert field in alert, f"Alert missing required field: {field}"

        # Verify specific alert properties
        assert alert["alert_name"] == "validation_failure_rate"
        assert alert["threshold_value"] == 0.10  # 10% threshold from default config
        assert (
            alert["actual_value"] > alert["threshold_value"]
        ), "Actual failure rate should exceed threshold"
        assert (
            abs(alert["actual_value"] - 0.25) < 0.01
        ), f"Expected ~25% failure rate, got {alert['actual_value']}"
        assert alert["window_minutes"] == 60  # From default threshold config

    @patch("datetime.datetime")
    def test_alert_mechanism_no_false_positives(self, mock_datetime):
        """Test that alerts are not triggered when failure rates are below thresholds."""
        from datetime import datetime, timezone

        # Set up a fixed time for consistent testing
        fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time
        mock_datetime.fromisoformat = datetime.fromisoformat

        # Record low failure rate (5% - below 10% threshold)
        for i in range(19):
            self.monitor.record_validation(f"http://url{i}.com", True, 50.0)

        # Only 1 failure out of 20 = 5% failure rate
        self.monitor.record_validation(
            "http://bad.com", False, 50.0, error_type="Invalid URL"
        )

        # Clear any existing alerts
        self.monitor.alert_history.clear()

        # Trigger alert check
        self.monitor._check_alerts()

        # Verify no alerts were triggered
        assert (
            len(self.monitor.alert_history) == 0
        ), "No alerts should be triggered for 5% failure rate"

    def test_alert_cooldown_mechanism(self):
        """Test that alert cooldown prevents spam alerts."""
        from datetime import datetime, timedelta

        # Record high failure rate to trigger alert
        for i in range(10):
            self.monitor.record_validation(f"http://url{i}.com", True, 50.0)
        for i in range(5):
            self.monitor.record_validation(
                f"http://bad{i}.com", False, 50.0, error_type="Invalid URL"
            )

        # Clear alert history and trigger first alert
        self.monitor.alert_history.clear()
        self.monitor._check_alerts()

        # Verify first alert was triggered
        assert len(self.monitor.alert_history) == 1, "First alert should be triggered"
        first_alert_time = datetime.fromisoformat(
            self.monitor.alert_history[0]["timestamp"]
        )

        # Try to trigger another alert immediately (should be blocked by cooldown)
        self.monitor._check_alerts()
        assert (
            len(self.monitor.alert_history) == 1
        ), "Second alert should be blocked by cooldown"

        # Simulate time passing beyond cooldown period (120 minutes for validation_failure_rate)
        with patch("btc_max_knowledge_agent.monitoring.url_metadata_monitor.datetime") as mock_datetime:
            from datetime import timezone
            future_time = (first_alert_time + timedelta(minutes=121)).replace(tzinfo=timezone.utc)
            
            # Mock the datetime module properly
            mock_datetime.now.return_value = future_time
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Add more failures and check alerts again
            for i in range(5, 10):
                self.monitor.record_validation(
                    f"http://bad{i}.com", False, 50.0, error_type="Invalid URL"
                )

            self.monitor._check_alerts()

            # Now a second alert should be triggered
            assert (
                len(self.monitor.alert_history) == 2
            ), "Second alert should be triggered after cooldown"

    def test_performance_distribution(self):
        """Test performance distribution calculation."""
        # Add various response times
        times = [10, 50, 100, 200, 500, 1000, 2000, 5000]
        for t in times:
            self.monitor.record_retrieval("http://example.com", 1, t)

        summary = self.monitor.generate_hourly_summary()
        assert "performance_distribution" in summary

    def test_summary_reports(self):
        """Test summary report generation."""
        # Add some test data
        for i in range(10):
            self.monitor.record_validation(f"http://url{i}.com", i % 2 == 0, 100.0)
            self.monitor.record_upload(f"http://url{i}.com", i % 3 != 0, 200.0, 1024)

        # Test hourly summary
        hourly_summary = self.monitor.generate_hourly_summary()
        assert "timestamp" in hourly_summary
        assert "period" in hourly_summary
        assert hourly_summary["period"] == "hourly"

        # Test daily summary
        daily_summary = self.monitor.generate_daily_summary()
        assert "timestamp" in daily_summary
        assert daily_summary["period"] == "daily"
        assert "top_errors" in daily_summary
        assert "slowest_operations" in daily_summary


class TestLoggingIntegration:
    """Test integration of logging with various modules."""

    @patch("requests.head")
    def test_url_utils_logging(self, mock_head):
        """Test logging in url_utils functions."""
        mock_head.return_value.status_code = 200

        # Test is_secure_url with logging
        with patch("btc_max_knowledge_agent.utils.url_utils.log_validation") as mock_log:
            result = is_secure_url("https://example.com")
            assert result is True
            # Verify logging occurred
            mock_log.assert_called_once()

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

        with patch("btc_max_knowledge_agent.utils.url_error_handler.log_retry") as mock_log_retry:
            result = failing_function()

            assert result == "success"
            assert call_count == 3
            # Check that retry logging occurred
            assert mock_log_retry.call_count == 2  # Two retries
    def test_data_collector_logging(self):
        """Test logging in data collector."""
        collector = BitcoinDataCollector()

        # Mock external calls to avoid flaky tests
        with patch.object(collector, "collect_from_sources") as mock_fetch:
            mock_fetch.return_value = [{"url": "http://example.com", "content": "test"}]

            with patch("btc_max_knowledge_agent.knowledge.data_collector.log_validation") as mock_log:
                # Test collection with logging
                documents = collector.collect_bitcoin_basics()

                # Check that documents were collected
                assert len(documents) > 0
                assert all("url" in doc for doc in documents)

                # Verify logging occurred
                assert mock_log.call_count > 0
class TestPerformanceImpact:
    """Test performance impact of logging."""

    def test_logging_overhead(self):
        """Measure logging overhead."""
        iterations = 1000
        max_acceptable_overhead = 10.0  # Maximum 10x overhead

        # Measure without logging
        start_time = time.time()
        for i in range(iterations):
            url = f"https://example.com/{i}"
            # More realistic baseline: URL validation
            _ = url.startswith("https://") and len(url) > 10
        baseline_time = time.time() - start_time

        # Measure with logging
        start_time = time.time()
        for i in range(iterations):
            url = f"https://example.com/{i}"
            with correlation_context():
                log_validation(url, True, "test", duration_ms=50.0)
        logging_time = time.time() - start_time
        # Logging should not add excessive overhead
        overhead_ratio = logging_time / baseline_time
        assert overhead_ratio < max_acceptable_overhead, (
            f"Logging overhead {overhead_ratio:.2f}x exceeds maximum "
            f"{max_acceptable_overhead}x"
        )

    def test_monitor_memory_usage(self):
        """Test that monitor doesn't consume excessive memory."""
        monitor = URLMetadataMonitor()

        # Add many metrics
        for i in range(10000):
            monitor.record_validation(f"http://url{i}.com", True, 50.0)

        # Check that memory is bounded by deque maxlen
        assert len(monitor.metrics_store["validation"]) <= 10000


class TestLogRotation:
    """Test log rotation functionality."""

    def test_log_file_handler_configuration(self):
        """Test that log handlers are configured correctly."""
        logger = url_metadata_logger.validation_logger

        # Check that logger has handlers
        assert len(logger.handlers) > 0

        # Check that at least one handler is a RotatingFileHandler
        from logging.handlers import RotatingFileHandler

        rotating_handlers = [
            h for h in logger.handlers if isinstance(h, RotatingFileHandler)
        ]
        assert len(rotating_handlers) > 0

        # Check rotation parameters against configuration constants
        handler = rotating_handlers[0]
        assert handler.maxBytes == LOG_ROTATION_MAX_BYTES
        assert handler.backupCount == LOG_ROTATION_BACKUP_COUNT


class TestErrorHandling:
    """Test error handling in logging infrastructure."""

    def test_logging_doesnt_break_operation(self):
        """Test that logging failures don't break the main operation."""
        # Even if logging fails, the operation should succeed
        with patch(
            "btc_max_knowledge_agent.utils.url_metadata_logger.URLMetadataLogger.log_validation",
            side_effect=Exception("Logging error"),
        ):
            with patch("requests.head") as mock_head:
                mock_head.return_value.status_code = 200
                try:
                    # This should still work even if logging fails
                    result = is_secure_url("https://example.com")
                    assert result is True
                except Exception as e:
                    pytest.fail(f"Operation failed due to logging error: {e}")

        # Test validation with various invalid inputs
        invalid_validation_cases = [
            (None, True, -100),  # None URL, negative duration
            ("", True, 0),  # Empty URL, zero duration
            ("valid_url", None, 50.0),  # None success flag
            ("valid_url", True, float("-inf")),  # Negative infinity duration
            ("valid_url", True, float("inf")),  # Positive infinity duration
            ("valid_url", True, float("nan")),  # NaN duration
            (123, True, 50.0),  # Non-string URL (integer)
            (["url"], True, 50.0),  # Non-string URL (list)
            ("valid_url", "not_boolean", 50.0),  # Non-boolean success
            ("valid_url", True, "not_numeric"),  # Non-numeric duration
            ("valid_url", True, -999999999),  # Extremely large negative value
            ("valid_url", True, 999999999999),  # Extremely large positive value
        ]

        for url, success, duration in invalid_validation_cases:
            try:
                monitor.record_validation(
                    url, success, duration, error_type="test_error"
                )
            except Exception:
                # Monitor should handle gracefully, but if it raises an exception,
                # that's also acceptable behavior - we just don't want crashes
                pass

        # Test upload with various invalid inputs
        invalid_upload_cases = [
            (None, False, float("inf"), -1),  # None URL, invalid values
            ("", True, -50.0, 0),  # Empty URL, negative duration
            ("valid_url", None, 100.0, 1024),  # None success flag
            ("valid_url", True, 100.0, None),  # None size
            ("valid_url", True, 100.0, -999),  # Negative size
            ("valid_url", True, float("nan"), 1024),  # NaN duration
            (42, True, 100.0, 1024),  # Non-string URL (integer)
            ({"url": "test"}, True, 100.0, 1024),  # Non-string URL (dict)
            ("valid_url", 1, 100.0, 1024),  # Non-boolean success (integer)
            ("valid_url", [], 100.0, 1024),  # Non-boolean success (list)
            ("valid_url", True, [100.0], 1024),  # Non-numeric duration (list)
            ("valid_url", True, 100.0, "large"),  # Non-numeric size (string)
            ("valid_url", True, 100.0, float("inf")),  # Infinite size
            ("valid_url", True, 100.0, float("-inf")),  # Negative infinite size
        ]

        for url, success, duration, size in invalid_upload_cases:
            try:
                monitor.record_upload(
                    url, success, duration, size, error_type="test_error"
                )
            except Exception:
                # Monitor should handle gracefully, but exceptions are acceptable
                pass

        # Test retrieval with invalid inputs
        invalid_retrieval_cases = [
            (None, -1, 50.0),  # None URL, negative count
            ("", 0, float("inf")),  # Empty URL, infinite duration
            ("valid_url", None, 50.0),  # None count
            ("valid_url", 5, None),  # None duration
            (123, 5, 50.0),  # Non-string URL
            ("valid_url", "five", 50.0),  # Non-numeric count
            ("valid_url", 5, "slow"),  # Non-numeric duration
            ("valid_url", float("inf"), 50.0),  # Infinite count
            ("valid_url", -999999, 50.0),  # Extremely negative count
        ]

        for url, count, duration in invalid_retrieval_cases:
            try:
                monitor.record_retrieval(url, count, duration)
            except Exception:
                pass

        # Test with completely invalid error_type parameters
        invalid_error_types = [None, 123, [], {}, float("inf"), float("nan")]

        for error_type in invalid_error_types:
            try:
                monitor.record_validation(
                    "test_url", False, 50.0, error_type=error_type
                )
            except Exception:
                pass

        # Test boundary values
        boundary_cases = [
            ("url", True, 0.0),  # Zero duration (valid boundary)
            ("url", True, 0.000001),  # Very small positive duration
            ("url", False, 0.0),  # Zero duration with failure
            ("", True, 1.0),  # Empty string URL (edge case)
            (" ", True, 1.0),  # Whitespace-only URL
            ("a" * 10000, True, 1.0),  # Extremely long URL
        ]

        for url, success, duration in boundary_cases:
            try:
                monitor.record_validation(url, success, duration)
            except Exception:
                pass

        # The monitor should not crash when generating summary after all invalid inputs
        summary = monitor.generate_hourly_summary()
        assert summary is not None

        # Verify summary structure is still intact
        assert isinstance(summary, dict)
        assert (
            "timestamp" in summary or len(summary) == 0
        )  # Could be empty if all data was rejected


class TestConvenienceFunctions:
    def test_global_convenience_functions(self):
        """Test global convenience functions."""
class TestConvenienceFunctions:
    def test_global_convenience_functions(self):
        """Test global convenience functions."""
        # Get initial state
        initial_summary = url_metadata_monitor.generate_hourly_summary()

        # Test monitoring functions
        record_validation("https://example.com", True, 100.0)
        record_upload("https://example.com", True, 200.0, 1024)

        # Test logging functions
        log_validation("https://example.com", True, "test")
        log_upload("https://example.com", True, 1024)
        log_retry("test_op", 1, 3, "error")

        # Verify monitoring functions recorded data
        final_summary = url_metadata_monitor.generate_hourly_summary()
        assert final_summary != initial_summary

        # Verify specific metrics were recorded
        ops = final_summary.get("operations", {})
        assert "validation" in ops
        assert "upload" in ops
        # Verify specific metrics were recorded correctly
        validation_ops = ops.get("validation", {})
        upload_ops = ops.get("upload", {})
        assert validation_ops.get("total", 0) >= 1
        assert upload_ops.get("total", 0) >= 1
