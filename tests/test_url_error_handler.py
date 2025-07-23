"""
Comprehensive unit tests for URL error handling module.

This module tests:
- Custom exception hierarchy
- Exponential backoff retry decorator with various scenarios
- Graceful degradation utilities
- Fallback URL generation strategies
- Null-safe metadata operations
"""

from unittest.mock import call, patch

import pytest

from btc_max_knowledge_agent.utils.url_error_handler import (
    FallbackURLStrategy,
    GracefulDegradation,
    RetryExhaustedError,
    URLMetadataError,
    URLMetadataUploadError,
    URLRetrievalError,
    URLValidationError,
    exponential_backoff_retry,
    retry_url_retrieval,
    retry_url_upload,
    retry_url_validation,
)


class TestCustomExceptions:
    """Test custom exception hierarchy."""

    def test_url_metadata_error_base(self):
        """Test base URLMetadataError exception."""
        # Test with message only
        error = URLMetadataError("Test error message")
        assert str(error) == "Test error message"
        assert error.url is None
        assert error.original_error is None

        # Test with URL
        error = URLMetadataError("Test error", url="https://example.com")
        assert "Test error (URL: https://example.com)" in str(error)
        assert error.url == "https://example.com"

        # Test with original error
        original = ValueError("Original error")
        error = URLMetadataError("Test error", original_error=original)
        assert "Original error: Original error" in str(error)
        assert error.original_error == original

        # Test with both URL and original error
        error = URLMetadataError(
            "Test error", url="https://example.com", original_error=original
        )
        assert "Test error (URL: https://example.com)" in str(error)
        assert "Original error: Original error" in str(error)

    def test_url_validation_error(self):
        """Test URLValidationError exception."""
        error = URLValidationError("Invalid URL format", url="not-a-url")
        assert isinstance(error, URLMetadataError)
        assert "Invalid URL format" in str(error)
        assert "(URL: not-a-url)" in str(error)

    def test_url_metadata_upload_error(self):
        """Test URLMetadataUploadError exception."""
        original = ConnectionError("Network failure")
        error = URLMetadataUploadError(
            "Failed to upload metadata",
            url="https://example.com",
            original_error=original,
        )
        assert isinstance(error, URLMetadataError)
        assert "Failed to upload metadata" in str(error)
        assert "Network failure" in str(error)

    def test_url_retrieval_error(self):
        """Test URLRetrievalError exception."""
        error = URLRetrievalError(
            "Failed to retrieve metadata", url="https://example.com/doc"
        )
        assert isinstance(error, URLMetadataError)
        assert error.url == "https://example.com/doc"

    def test_retry_exhausted_error(self):
        """Test RetryExhaustedError exception."""
        last_error = TimeoutError("Connection timed out")
        error = RetryExhaustedError(
            "All retries failed", attempts=5, last_error=last_error
        )
        assert isinstance(error, URLMetadataError)
        assert error.attempts == 5
        assert error.original_error == last_error
        assert "Connection timed out" in str(error)


class TestExponentialBackoffRetry:
    """Test exponential backoff retry decorator."""

    def test_successful_on_first_attempt(self):
        """Test function succeeds on first attempt."""

        @exponential_backoff_retry(max_retries=3)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_retry_and_succeed(self):
        """Test function fails then succeeds."""
        attempt_count = 0

        @exponential_backoff_retry(max_retries=3, initial_delay=0.01, jitter=False)
        def eventually_successful():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError(f"Attempt {attempt_count} failed")
            return "success"

        result = eventually_successful()
        assert result == "success"
        assert attempt_count == 3

    def test_all_retries_exhausted_with_exception(self):
        """Test all retries exhausted, raises exception."""
        attempt_count = 0

        @exponential_backoff_retry(
            max_retries=2, initial_delay=0.01, raise_on_exhaust=True
        )
        def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError(f"Attempt {attempt_count} failed")

        with pytest.raises(RetryExhaustedError) as exc_info:
            always_fails()

        assert exc_info.value.attempts == 3  # 2 retries + 1 initial
        assert "Failed after 3 attempts" in str(exc_info.value)
        assert attempt_count == 3

    def test_all_retries_exhausted_with_fallback(self):
        """Test all retries exhausted, returns fallback."""
        attempt_count = 0

        @exponential_backoff_retry(
            max_retries=2,
            initial_delay=0.01,
            raise_on_exhaust=False,
            fallback_result="fallback value",
        )
        def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError(f"Attempt {attempt_count} failed")

        result = always_fails()
        assert result == "fallback value"
        assert attempt_count == 3

    def test_specific_exception_handling(self):
        """Test retry only on specific exceptions."""

        @exponential_backoff_retry(
            max_retries=3,
            initial_delay=0.01,
            exceptions=(ConnectionError, TimeoutError),
        )
        def specific_exception_function(error_type):
            if error_type == "connection":
                raise ConnectionError("Connection failed")
            elif error_type == "value":
                raise ValueError("Value error")
            return "success"

        # Should retry on ConnectionError and succeed
        result = specific_exception_function("success")
        assert result == "success"

        # Should not retry on ValueError (not in exceptions tuple)
        with pytest.raises(ValueError):
            specific_exception_function("value")

    @patch("time.sleep")
    def test_exponential_backoff_timing(self, mock_sleep):
        """Test exponential backoff delay calculation."""
        attempt_count = 0

        @exponential_backoff_retry(
            max_retries=3,
            initial_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=False,
        )
        def failing_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 3:
                raise ConnectionError("Failed")
            return "success"

        result = failing_function()
        assert result == "success"

        # Check sleep was called with correct delays
        expected_calls = [
            call(1.0),  # First retry: 1.0 * 2^0 = 1.0
            call(2.0),  # Second retry: 1.0 * 2^1 = 2.0
            call(4.0),  # Third retry: 1.0 * 2^2 = 4.0
        ]
        mock_sleep.assert_has_calls(expected_calls)

    @patch("time.sleep")
    def test_max_delay_enforcement(self, mock_sleep):
        """Test that delays don't exceed max_delay."""
        attempt_count = 0

        @exponential_backoff_retry(
            max_retries=5,
            initial_delay=1.0,
            max_delay=5.0,
            exponential_base=3.0,
            jitter=False,
        )
        def failing_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 5:
                raise ConnectionError("Failed")
            return "success"

        result = failing_function()
        assert result == "success"

        # Check that no delay exceeds max_delay
        for call_args in mock_sleep.call_args_list:
            delay = call_args[0][0]
            assert delay <= 5.0

    @patch("random.random")
    @patch("time.sleep")
    def test_jitter_application(self, mock_sleep, mock_random):
        """Test jitter is applied when enabled."""
        mock_random.return_value = 0.5  # Fixed random value for testing
        attempt_count = 0

        @exponential_backoff_retry(max_retries=1, initial_delay=1.0, jitter=True)
        def failing_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 1:
                raise ConnectionError("Failed")
            return "success"

        result = failing_function()
        assert result == "success"

        # With jitter, delay should be: 1.0 * (0.5 + 0.5 * 0.5) = 0.75
        mock_sleep.assert_called_once_with(0.75)

    @patch("utils.url_metadata_logger.log_retry")
    def test_retry_logging(self, mock_log_retry):
        """Test that retries are properly logged."""
        attempt_count = 0

        @exponential_backoff_retry(max_retries=2, initial_delay=0.01)
        def logged_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ConnectionError("Test error")
            return "success"

        result = logged_function()
        assert result == "success"

        # Should have logged one retry attempt
        assert mock_log_retry.call_count == 1
        mock_log_retry.assert_called_with(
            operation="logged_function", attempt=1, max_attempts=3, error="Test error"
        )


class TestFallbackURLStrategy:
    """Test fallback URL generation strategies."""

    def test_domain_only_url_valid(self):
        """Test extracting domain-only URL from valid URL."""
        test_cases = [
            ("https://example.com/path/to/page", "https://example.com"),
            (
                "http://subdomain.example.com/page?query=1",
                "http://subdomain.example.com",
            ),
            ("https://example.com:8080/resource", "https://example.com:8080"),
            ("https://user:pass@example.com/path", "https://user:pass@example.com"),
        ]

        for original, expected in test_cases:
            result = FallbackURLStrategy.domain_only_url(original)
            assert result == expected

    def test_domain_only_url_invalid(self):
        """Test domain extraction from invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "",
            None,
            "://missing-scheme.com",
            "https://",
        ]

        for url in invalid_urls:
            result = FallbackURLStrategy.domain_only_url(url)
            assert result is None

    @patch("logging.error")
    def test_domain_only_url_exception_handling(self, mock_logger):
        """Test exception handling in domain extraction."""
        # Force an exception by passing non-string
        result = FallbackURLStrategy.domain_only_url(12345)
        assert result is None
        mock_logger.assert_called_once()

    def test_placeholder_url_with_identifier(self):
        """Test placeholder URL generation with identifier."""
        result = FallbackURLStrategy.placeholder_url("doc123")
        assert result == "https://placeholder.local/doc123"

        result = FallbackURLStrategy.placeholder_url("user/456")
        assert result == "https://placeholder.local/user/456"

    def test_placeholder_url_without_identifier(self):
        """Test placeholder URL generation without identifier."""
        result = FallbackURLStrategy.placeholder_url()
        assert result == "https://placeholder.local/document"

        result = FallbackURLStrategy.placeholder_url(None)
        assert result == "https://placeholder.local/document"

        result = FallbackURLStrategy.placeholder_url("")
        assert result == "https://placeholder.local/document"

    def test_empty_url(self):
        """Test empty URL generation."""
        result = FallbackURLStrategy.empty_url()
        assert result == ""
        assert isinstance(result, str)


class TestGracefulDegradation:
    """Test graceful degradation utilities."""

    def test_safe_url_operation_success(self):
        """Test safe URL operation wrapper with successful operation."""

        def successful_operation(url: str) -> str:
            return f"processed: {url}"

        safe_op = GracefulDegradation.safe_url_operation(
            successful_operation, operation_name="test_operation"
        )

        result = safe_op("https://example.com")
        assert result == "processed: https://example.com"

    @patch("logging.error")
    def test_safe_url_operation_failure_no_fallback(self, mock_logger):
        """Test safe URL operation with failure and no fallback."""

        def failing_operation(url: str) -> str:
            raise ValueError("Operation failed")

        safe_op = GracefulDegradation.safe_url_operation(
            failing_operation, operation_name="test_operation"
        )

        result = safe_op("https://example.com")
        assert result is None
        assert mock_logger.call_count == 2  # Initial error + exhausted message

    @patch("logging.info")
    @patch("logging.warning")
    @patch("logging.error")
    def test_safe_url_operation_with_fallbacks(
        self, mock_error, mock_warning, mock_info
    ):
        """Test safe URL operation with fallback strategies."""

        def failing_operation(url: str) -> str:
            raise ValueError("Primary operation failed")

        def fallback1(url: str) -> str:
            raise ConnectionError("Fallback 1 failed")

        def fallback2(url: str) -> str:
            return "fallback result"

        safe_op = GracefulDegradation.safe_url_operation(
            failing_operation,
            fallback_strategies=[fallback1, fallback2],
            operation_name="test_operation",
        )

        result = safe_op("https://example.com")
        assert result == "fallback result"

        # Check logging
        mock_error.assert_called()
        mock_info.assert_called()  # Fallback attempts
        mock_warning.assert_called()  # Fallback 1 failure

    def test_null_safe_metadata_empty_input(self):
        """Test null-safe metadata with empty input."""
        result = GracefulDegradation.null_safe_metadata(None)
        assert result == {"url": ""}

        result = GracefulDegradation.null_safe_metadata({})
        assert result == {"url": ""}

    def test_null_safe_metadata_with_none_values(self):
        """Test null-safe metadata with None values."""
        metadata = {
            "title": "Test Document",
            "url": None,
            "source_url": None,
            "document_url": None,
            "reference_url": None,
            "other_field": "value",
        }

        result = GracefulDegradation.null_safe_metadata(metadata)

        assert result["title"] == "Test Document"
        assert result["url"] == ""
        assert result["source_url"] == ""
        assert result["document_url"] == ""
        assert result["reference_url"] == ""
        assert result["other_field"] == "value"

    def test_null_safe_metadata_preserves_valid_urls(self):
        """Test null-safe metadata preserves valid URLs."""
        metadata = {
            "url": "https://example.com",
            "source_url": "https://source.com",
            "document_url": None,
            "title": "Test",
        }

        result = GracefulDegradation.null_safe_metadata(metadata)

        assert result["url"] == "https://example.com"
        assert result["source_url"] == "https://source.com"
        assert result["document_url"] == ""
        assert result["title"] == "Test"

    def test_create_partial_result(self):
        """Test creation of partial results."""
        success_data = {"processed_count": 8, "indexed_count": 6}
        failed_ops = ["url_validation", "metadata_extraction"]
        error_details = {
            "url_validation": "Invalid URL format",
            "metadata_extraction": "Timeout occurred",
        }

        result = GracefulDegradation.create_partial_result(
            success_data, failed_ops, error_details
        )

        assert result["status"] == "partial_success"
        assert result["data"] == success_data
        assert result["errors"]["failed_operations"] == failed_ops
        assert result["errors"]["error_count"] == 2
        assert result["errors"]["details"] == error_details

    def test_create_partial_result_without_error_details(self):
        """Test partial result creation without error details."""
        success_data = {"items": ["a", "b", "c"]}
        failed_ops = ["operation1"]

        result = GracefulDegradation.create_partial_result(success_data, failed_ops)

        assert result["status"] == "partial_success"
        assert result["data"] == success_data
        assert result["errors"]["failed_operations"] == failed_ops
        assert result["errors"]["error_count"] == 1
        assert "details" not in result["errors"]


class TestConvenienceDecorators:
    """Test convenience retry decorators."""

    def test_retry_url_validation_decorator(self):
        """Test retry_url_validation decorator configuration."""

        @retry_url_validation
        def validate_function():
            raise URLValidationError("Validation failed")

        # Should not raise exception (raise_on_exhaust=False)
        result = validate_function()
        assert result is None  # Default fallback

    def test_retry_url_upload_decorator(self):
        """Test retry_url_upload decorator configuration."""

        @retry_url_upload
        def upload_function():
            raise URLMetadataUploadError("Upload failed")

        # Should raise exception after retries (raise_on_exhaust=True)
        with pytest.raises(RetryExhaustedError):
            upload_function()

    def test_retry_url_retrieval_decorator(self):
        """Test retry_url_retrieval decorator configuration."""

        @retry_url_retrieval
        def retrieval_function():
            raise URLRetrievalError("Retrieval failed")

        # Should return fallback result (empty dict)
        result = retrieval_function()
        assert result == {}


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple components."""

    def test_retry_with_fallback_strategy(self):
        """Test retry decorator with fallback URL strategy."""
        attempt_count = 0

        @exponential_backoff_retry(
            max_retries=2, initial_delay=0.01, raise_on_exhaust=False
        )
        def process_url(url: str) -> str:
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count <= 2:
                raise URLValidationError("Invalid URL", url=url)

            # On third attempt, use fallback
            return (
                FallbackURLStrategy.domain_only_url(url)
                or FallbackURLStrategy.placeholder_url()
            )

        result = process_url("https://example.com/invalid/path")
        assert attempt_count == 3

        assert result == "https://example.com"

    def test_graceful_degradation_with_retry(self):
        """Test graceful degradation combined with retry logic."""

        @retry_url_validation
        def validate_with_fallback(url: str) -> dict:
            if not url or url == "invalid":
                raise URLValidationError("Invalid URL")
            return {"url": url, "valid": True}

        # Create safe operation with fallback
        def fallback_validation(url: str) -> dict:
            return GracefulDegradation.null_safe_metadata({"url": url})

        safe_validate = GracefulDegradation.safe_url_operation(
            validate_with_fallback,
            fallback_strategies=[fallback_validation],
            operation_name="validation",
        )

        # Test with invalid URL
        result = safe_validate("invalid")
        assert result == {"url": "invalid"}

        # Test with valid URL
        result = safe_validate("https://example.com")
        assert result == {"url": "https://example.com", "valid": True}

    @patch("btc_max_knowledge_agent.utils.url_metadata_logger.log_retry")
    @patch(
        "monitoring.url_metadata_monitor.url_metadata_monitor"
    )
    def test_monitoring_integration(self, mock_monitor, mock_log_retry):
        """Test integration with monitoring and logging."""

        @exponential_backoff_retry(max_retries=1, initial_delay=0.01)
        def monitored_operation():
            raise ConnectionError("Network error")

        with pytest.raises(RetryExhaustedError):
            monitored_operation()

        # Verify logging was called
        assert mock_log_retry.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
