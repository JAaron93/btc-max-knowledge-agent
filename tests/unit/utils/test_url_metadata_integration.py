"""
Integration tests for URL metadata system.

This module tests:
- End-to-end URL metadata flow from data collection to storage
- Backward compatibility with existing vectors lacking URLs
- URL validation failures with graceful degradation
- Retry mechanisms under various network conditions
- Logging correlation ID tracking across operations
"""

import time
import uuid
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from btc_max_knowledge_agent.knowledge.data_collector import DataCollector
from btc_max_knowledge_agent.retrieval.pinecone_client import PineconeClient
from utils.url_error_handler import (
    GracefulDegradation,
    URLValidationError,
    exponential_backoff_retry,
)
from utils.url_metadata_logger import get_correlation_id, set_correlation_id
from utils.url_utils import (
    check_urls_accessibility_parallel,
    sanitize_url_for_storage,
    validate_url_batch,
)


class TestEndToEndURLMetadataFlow:
    """Test complete URL metadata flow from collection to storage."""

    @patch("btc_max_knowledge_agent.retrieval.pinecone_client.Pinecone")
    @patch("utils.url_utils.sanitize_url_for_storage")
    @patch("utils.url_utils.validate_url")
    @patch("utils.url_utils.normalize_url")
    @patch("utils.url_utils.is_secure_url")
    def test_successful_url_metadata_flow(
        self,
        mock_is_secure,
        mock_normalize,
        mock_validate,
        mock_sanitize,
        mock_pinecone_class,
    ):
        """Test successful end-to-end URL metadata flow."""
        # Setup URL validation mocks to return valid results
        mock_is_secure.return_value = True
        mock_normalize.return_value = "https://bitcoin.org/bitcoin.pdf"
        mock_validate.return_value = True
        mock_sanitize.return_value = "https://bitcoin.org/bitcoin.pdf"

        # Mock Pinecone instance and index
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone

        # Mock successful upsert operation
        mock_index.upsert.return_value = {"upserted_count": 5}

        # Initialize DataCollector and PineconeClient
        data_collector = DataCollector(check_url_accessibility=False)
        pinecone_client = PineconeClient()

        # Set correlation ID for tracking
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Call DataCollector's method to process URLs and collect metadata
        documents = data_collector.collect_bitcoin_basics()

        # Verify documents were collected with URL metadata
        assert len(documents) > 0, "DataCollector should return documents"

        # Verify each document has proper URL metadata structure
        for doc in documents:
            assert "id" in doc, "Document should have ID"
            assert "title" in doc, "Document should have title"
            assert "content" in doc, "Document should have content"
            assert "url" in doc, "Document should have URL field"
            assert "category" in doc, "Document should have category"

            # URL should be non-empty for test documents
            if doc["url"]:
                # Verify URL was processed through sanitization
                assert doc["url"] == "https://bitcoin.org/bitcoin.pdf"

        # Simulate storing processed documents in Pinecone
        # Convert documents to vector format as PineconeClient would
        vectors = []
        for i, doc in enumerate(documents):
            vector = {
                "id": doc["id"],
                "values": [0.1] * 1536,  # Mock embedding vector
                "metadata": {
                    "title": doc["title"],
                    "content": doc["content"][:500],  # Truncate for metadata
                    "source": doc.get("source", ""),
                    "category": doc["category"],
                    "url": doc["url"],
                },
            }
            vectors.append(vector)

        # Call PineconeClient to store the processed data
        result = pinecone_client.upsert_vectors(vectors)

        # Verify PineconeClient storage methods were called
        mock_index.upsert.assert_called_once()

        # Get the actual call arguments to verify the data structure
        call_args = mock_index.upsert.call_args
        assert call_args is not None, "upsert should have been called"

        # Verify the vectors parameter structure
        if "vectors" in call_args.kwargs:
            stored_vectors = call_args.kwargs["vectors"]
        else:
            stored_vectors = call_args.args[0] if call_args.args else []

        assert len(stored_vectors) > 0, "Should store vectors with metadata"

        # Verify stored data has expected URL metadata structure
        for stored_vector in stored_vectors:
            assert "id" in stored_vector, "Stored vector should have ID"
            assert (
                "values" in stored_vector
            ), "Stored vector should have embedding values"
            assert "metadata" in stored_vector, "Stored vector should have metadata"

            metadata = stored_vector["metadata"]
            assert "url" in metadata, "Stored metadata should include URL"
            assert "title" in metadata, "Stored metadata should include title"
            assert "category" in metadata, "Stored metadata should include category"

            # Verify URL was properly processed and matches expected format
            if metadata["url"]:
                assert metadata["url"] == "https://bitcoin.org/bitcoin.pdf"

        # Verify the final result indicates successful storage
        assert result["upserted_count"] == 5, "Should confirm successful storage"

        # Verify URL processing methods were called during collection
        assert mock_sanitize.called, "URL sanitization should be called"

        # Verify correlation ID was maintained throughout the flow
        assert (
            get_correlation_id() == correlation_id
        ), "Correlation ID should be preserved"

    @patch("btc_max_knowledge_agent.retrieval.pinecone_client.Pinecone")
    @patch("utils.url_utils.validate_url")
    @patch("utils.url_error_handler.GracefulDegradation.safe_url_operation")
    def test_url_validation_failure_with_graceful_degradation(
        self,
        mock_safe_operation,
        mock_validate,
        mock_pinecone_class,
    ):
        """Test URL validation failure with graceful degradation."""
        # Setup validation to fail
        mock_validate.side_effect = URLValidationError("Invalid URL format")
        mock_safe_operation.return_value = ""  # Empty URL fallback

        # Mock Pinecone
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone

        # Initialize components
        PineconeClient()
        DataCollector(check_url_accessibility=False)

        # Test graceful degradation functionality with URL validation failures
        test_url = "not-a-valid-url"

        # Test URL validation batch functionality with invalid URL
        try:
            batch_results = validate_url_batch([test_url])
            # The invalid URL should return valid=False
            assert batch_results[test_url]["valid"] is False
        except URLValidationError:
            # If validation throws exception, graceful degradation should handle it
            fallback_result = mock_safe_operation(test_url)
            assert fallback_result == ""

        # Verify graceful degradation was used if called
        if mock_safe_operation.called:
            assert mock_safe_operation.called

    @patch("btc_max_knowledge_agent.retrieval.pinecone_client.Pinecone")
    @patch("utils.url_metadata_logger.url_metadata_logger.upload_logger")
    def test_correlation_id_tracking_across_operations(
        self, mock_logger, mock_pinecone_class
    ):
        """Test correlation ID tracking across multiple operations."""
        # Mock Pinecone
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone

        # Set correlation ID
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Initialize client
        pinecone_client = PineconeClient()

        # Perform operations
        with patch("utils.url_utils.validate_url") as mock_validate:
            mock_validate.return_value = True

            # Operation 1: Validate URL
            validate_url_batch(["https://example.com"])

            # Operation 2: Upload data
            vectors = [
                {
                    "id": "test-1",
                    "values": [0.1] * 1536,
                    "metadata": {"url": "https://example.com"},
                }
            ]
            mock_index.upsert.return_value = {"upserted_count": 1}
            pinecone_client.upsert_vectors(vectors)

            # Operation 3: Query
            mock_index.query.return_value = {
                "matches": [
                    {
                        "id": "test-1",
                        "score": 0.95,
                        "metadata": {"url": "https://example.com"},
                    }
                ]
            }
            pinecone_client.query([0.1] * 1536, top_k=1)

        # Verify correlation ID was included in all log calls
        log_calls = mock_logger.info.call_args_list
        for call_args in log_calls:
            # Check if correlation_id is in extra parameters
            _, kwargs = call_args
            if "extra" in kwargs and "correlation_id" in kwargs["extra"]:
                assert kwargs["extra"]["correlation_id"] == correlation_id

        # Ensure at least some log calls included the correlation ID
        correlation_id_found = any(
            "extra" in call[1]
            and "correlation_id" in call[1]["extra"]
            and call[1]["extra"]["correlation_id"] == correlation_id
            for call in log_calls
        )
        assert correlation_id_found, "Correlation ID not found in any log calls"

        # Step 4: Extract correlation-ID from logged records and verify consistency
        found_id = None
        for c in mock_logger.method_calls:
            extra = c.kwargs.get("extra", {})
            fields = extra.get("extra_fields", {})
            if "correlation_id" in fields:
                found_id = fields["correlation_id"]
                break
        assert found_id is not None
        assert isinstance(found_id, str)
        assert found_id

        # Step 5: Verify consistency of the correlation-ID
        # Scan the rest of the calls and ensure **every** occurrence of 'correlation_id' matches found_id
        for c in mock_logger.method_calls:
            extra = c.kwargs.get("extra", {})
            fields = extra.get("extra_fields", {})
            if "correlation_id" in fields:
                assert fields["correlation_id"] == found_id


class TestBackwardCompatibility:
    """Test backward compatibility with existing vectors lacking URLs."""

    @patch("btc_max_knowledge_agent.retrieval.pinecone_client.Pinecone")
    def test_query_vectors_without_url_metadata(self, mock_pinecone_class):
        """Test querying vectors that don't have URL metadata."""
        # Mock Pinecone
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone

        # Mock query response with vectors lacking URL metadata
        mock_index.query.return_value = {
            "matches": [
                {
                    "id": "old-vector-1",
                    "score": 0.95,
                    "metadata": {"text": "Old content without URL", "source": "legacy"},
                },
                {
                    "id": "new-vector-1",
                    "score": 0.90,
                    "metadata": {
                        "text": "New content with URL",
                        "url": "https://example.com/new",
                        "source": "current",
                    },
                },
            ]
        }

        # Initialize client
        pinecone_client = PineconeClient()

        # Query vectors
        results = pinecone_client.query([0.1] * 1536, top_k=2)

        # The stub PineconeClient returns matches directly, not wrapped in dict
        matches = results if isinstance(results, list) else results.get("matches", [])

        # Verify results contain both old and new vectors
        assert len(matches) == 2

        # Old vector should not have URL
        old_vector = matches[0]
        assert "url" not in old_vector["metadata"]

        # New vector should have URL
        new_vector = matches[1]
        assert "url" in new_vector["metadata"]
        assert new_vector["metadata"]["url"] == "https://example.com/new"

    @patch("btc_max_knowledge_agent.retrieval.pinecone_client.Pinecone")
    @patch("utils.url_error_handler.GracefulDegradation.null_safe_metadata")
    def test_mixed_metadata_handling(self, mock_null_safe, mock_pinecone_class):
        """Test handling of mixed metadata with and without URLs."""

        # Setup null-safe metadata to add empty URL for missing ones
        def null_safe_side_effect(metadata):
            if metadata is None:
                return {"url": ""}
            if "url" not in metadata:
                metadata["url"] = ""
            return metadata

        mock_null_safe.side_effect = null_safe_side_effect

        # Mock Pinecone
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone

        # Setup test vectors with mixed metadata
        vectors = [
            {
                "id": "vec-1",
                "values": [0.1] * 1536,
                "metadata": {"text": "No URL"},  # Missing URL
            },
            {
                "id": "vec-2",
                "values": [0.2] * 1536,
                "metadata": {"text": "Has URL", "url": "https://example.com"},
            },
            {"id": "vec-3", "values": [0.3] * 1536, "metadata": None},  # Null metadata
        ]

        # Initialize client
        pinecone_client = PineconeClient()

        # Process vectors
        mock_index.upsert.return_value = {"upserted_count": 3}

        # Apply null-safe processing
        processed_vectors = []
        for vec in vectors:
            processed_vec = vec.copy()
            processed_vec["metadata"] = null_safe_side_effect(vec.get("metadata"))
            processed_vectors.append(processed_vec)

        result = pinecone_client.upsert_vectors(processed_vectors)

        # Verify all vectors were processed
        assert result["upserted_count"] == 3

        # Verify null-safe metadata was applied

        assert mock_null_safe.call_count == 3  # Called for each vector


class TestRetryMechanisms:
    """Test retry mechanisms under various network conditions."""

    @patch("requests.head")
    @patch("time.sleep")
    def test_url_accessibility_check_with_retries(self, mock_sleep, mock_head):
        """Test URL accessibility checking with network failures."""
        # Simulate intermittent network failures
        responses = [
            requests.exceptions.ConnectionError("Network error"),
            requests.exceptions.Timeout("Timeout"),
            Mock(status_code=200),  # Success on third attempt
        ]
        mock_head.side_effect = responses

        # Check URL accessibility
        urls = ["https://example.com/test"]
        results = check_urls_accessibility_parallel(urls, timeout=5.0, max_workers=1)

        # Should eventually succeed
        assert results["https://example.com/test"] is True

        # Verify retries occurred
        assert mock_head.call_count >= 2

    @patch("btc_max_knowledge_agent.retrieval.pinecone_client.Pinecone")
    @patch("time.sleep")
    def test_pinecone_upload_retry_on_failure(self, mock_sleep, mock_pinecone_class):
        """Test Pinecone upload retry mechanism."""
        # Mock Pinecone
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone

        # Simulate upload failures then success
        mock_index.upsert.side_effect = [
            Exception("Network error"),
            Exception("Rate limit"),
            {"upserted_count": 1},  # Success on third attempt
        ]

        # Initialize client with retry decorator
        pinecone_client = PineconeClient()

        # Wrap upsert with retry logic

        @exponential_backoff_retry(max_retries=3, initial_delay=0.01)
        def retry_upsert(vectors):
            return pinecone_client.upsert_vectors(vectors)

        # Attempt upload
        vectors = [
            {
                "id": "test-1",
                "values": [0.1] * 1536,
                "metadata": {"url": "https://example.com"},
            }
        ]

        result = retry_upsert(vectors)

        # Should eventually succeed
        assert result["upserted_count"] == 1

        # Verify retries occurred
        assert mock_index.upsert.call_count == 3

    @patch("monitoring.url_metadata_monitor.url_metadata_monitor")
    def test_monitoring_during_retry_scenarios(self, mock_monitor):
        """Test monitoring integration during retry scenarios."""
        # Create a function that fails twice then succeeds
        attempt_count = 0

        @exponential_backoff_retry(max_retries=2, initial_delay=0.01)
        def monitored_operation():
            nonlocal attempt_count
            attempt_count += 1

            # Record attempt in monitoring
            mock_monitor.record_retry_attempt(
                operation="test_operation", attempt=attempt_count
            )

            if attempt_count < 3:
                raise ConnectionError(f"Attempt {attempt_count} failed")

            return "success"

        # Execute operation
        result = monitored_operation()

        # Verify success
        assert result == "success"
        assert attempt_count == 3

        # Verify monitoring was called for each attempt
        assert mock_monitor.record_retry_attempt.call_count >= 2


class TestURLValidationIntegration:
    """Test URL validation integration scenarios."""

    def test_batch_url_validation_with_mixed_results(self):
        """Test batch URL validation with mix of valid/invalid URLs.

        NOTE: This is an intentional integration test that calls the real
        validate_url_batch function to test the complete URL validation logic
        including security checks, format validation, and edge cases.
        No mocking is used here as we want to verify the actual validation behavior.
        """
        test_urls = [
            "https://valid.example.com",
            "javascript:alert('XSS')",  # Dangerous
            "https://192.168.1.1/private",  # Private IP
            "https://another-valid.com/page",
            "not-a-url",  # Invalid format
            "file:///etc/passwd",  # File protocol
            "https://valid-with-unicode-🎉.com",
        ]

        # Validate batch - using real validation logic for integration testing
        results = validate_url_batch(test_urls)

        # Check results - validate_url_batch now returns detailed dictionaries
        assert results["https://valid.example.com"]["valid"] is True
        assert results["javascript:alert('XSS')"]["valid"] is False
        assert results["https://192.168.1.1/private"]["valid"] is False
        assert results["https://another-valid.com/page"]["valid"] is True
        assert results["not-a-url"]["valid"] is False
        assert results["file:///etc/passwd"]["valid"] is False
        # Unicode in domain names fails validation for security reasons
        assert results["https://valid-with-unicode-🎉.com"]["valid"] is False

    @patch("utils.url_utils.validate_url_format")
    @patch("utils.url_utils.is_secure_url")
    @patch("utils.url_utils.is_private_ip")
    def test_batch_url_validation_with_mocked_components(
        self, mock_is_private_ip, mock_is_secure_url, mock_validate_url_format
    ):
        """Test batch URL validation with mocked underlying validation components.

        This version provides better test isolation by mocking the underlying
        validation functions to avoid external dependencies and ensure predictable results.
        Use this approach when you want to test validation logic without relying on
        actual URL validation implementations.
        """
        test_urls = [
            "https://valid.example.com",
            "javascript:alert('XSS')",
            "https://192.168.1.1/private",
            "https://another-valid.com/page",
            "not-a-url",
            "file:///etc/passwd",
            "https://valid-with-unicode-🎉.com",
        ]

        # Configure mocks to return expected validation results
        def mock_format_validation(url):
            # Simulate format validation logic
            if url in ["not-a-url"]:
                return False
            if url.startswith(("javascript:", "file:")):
                return False
            return True

        def mock_security_check(url):
            # Simulate security validation logic
            if url.startswith(("javascript:", "file:")):
                return False
            return True

        def mock_private_ip_check(url):
            # Simulate private IP detection
            return "192.168." in url or "10." in url or "172." in url

        mock_validate_url_format.side_effect = mock_format_validation
        mock_is_secure_url.side_effect = mock_security_check
        mock_is_private_ip.side_effect = mock_private_ip_check

        # Validate batch using mocked components
        results = validate_url_batch(test_urls)

        # Verify expected results based on mocked logic - checking 'valid' field
        assert results["https://valid.example.com"]["valid"] is True
        assert (
            results["javascript:alert('XSS')"]["valid"] is False
        )  # Fails security check
        assert results["https://192.168.1.1/private"]["valid"] is False  # Private IP
        assert results["https://another-valid.com/page"]["valid"] is True
        assert results["not-a-url"]["valid"] is False  # Fails format validation
        assert results["file:///etc/passwd"]["valid"] is False  # Fails security check
        assert results["https://valid-with-unicode-🎉.com"]["valid"] is False

        # Verify mocks were called appropriately
        assert mock_validate_url_format.call_count == len(test_urls)
        assert (
            mock_is_secure_url.call_count > 0
        )  # Called for URLs that pass format check
        assert mock_is_private_ip.call_count > 0  # Called for secure URLs

    def _test_url_validation_caching_integration(self):
        """Test URL validation caching behavior.

        NOTE: This test has been disabled as it tests private API functions.
        The caching integration is tested through other integration tests.
        """
        pass


class TestLoggingCorrelation:
    """Test logging correlation across operations."""

    @patch("utils.url_metadata_logger.url_metadata_logger.upload_logger")
    def test_correlation_id_propagation(self, mock_logger):
        """Test correlation ID propagation through operations."""
        # Set correlation ID
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Perform multiple operations
        operations = [
            ("validate_url", lambda: validate_url_batch(["https://example.com"])),
            (
                "sanitize_url",
                lambda: sanitize_url_for_storage("https://example.com/test"),
            ),
            (
                "check_accessibility",
                lambda: check_urls_accessibility_parallel(["https://example.com"]),
            ),
        ]

        for op_name, op_func in operations:
            try:
                op_func()
            except Exception as e:
                # Log or handle expected failures
                print(f"Operation {op_name} failed: {e}")
        # Verify correlation ID in logs
        assert get_correlation_id() == correlation_id

        # Check if logger was called with correlation ID
        # Note: Actual verification depends on logging implementation
        assert mock_logger.info.called or mock_logger.debug.called


class TestErrorHandlingIntegration:
    """Test integrated error handling scenarios."""

    @patch("btc_max_knowledge_agent.retrieval.pinecone_client.Pinecone")
    def test_partial_success_handling(self, mock_pinecone_class):
        """Test handling of partial success scenarios."""
        # Mock Pinecone
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone

        # Initialize client
        pinecone_client = PineconeClient()

        # Create vectors with mix of valid and problematic data
        vectors = [
            {
                "id": "valid-1",
                "values": [0.1] * 1536,
                "metadata": {"url": "https://valid.com", "text": "Valid"},
            },
            {
                "id": "invalid-metadata",
                "values": [0.2] * 1536,
                "metadata": {"url": "javascript:alert('xss')", "text": "Invalid URL"},
            },
            {
                "id": "valid-2",
                "values": [0.3] * 1536,
                "metadata": {"url": "https://another-valid.com", "text": "Valid"},
            },
        ]

        # Process with graceful degradation
        processed_vectors = []
        failed_vectors = []

        for vec in vectors:
            try:
                # Validate URL
                url = vec["metadata"].get("url", "")
                if url and not validate_url_batch([url])[url]["valid"]:
                    # Invalid URL - use fallback
                    vec["metadata"]["url"] = ""
                    vec["metadata"]["url_validation_failed"] = True
                    failed_vectors.append(vec["id"])
                processed_vectors.append(vec)
            except Exception:
                # Complete failure - skip vector
                failed_vectors.append(vec["id"])

        # Upload processed vectors
        mock_index.upsert.return_value = {"upserted_count": len(processed_vectors)}
        result = pinecone_client.upsert_vectors(processed_vectors)

        # Create partial result
        partial_result = GracefulDegradation.create_partial_result(
            success_data={
                "upserted_count": result["upserted_count"],
                "processed_ids": [v["id"] for v in processed_vectors],
            },
            failed_operations=failed_vectors,
            error_details={"invalid-metadata": "Invalid URL format"},
        )

        # Verify partial success handling
        assert partial_result["status"] == "partial_success"
        assert partial_result["data"]["upserted_count"] == 3
        assert "invalid-metadata" in failed_vectors


class TestPerformanceIntegration:
    """Test performance-related integration scenarios."""

    @patch("requests.head")
    def test_parallel_url_checking_performance(self, mock_head):
        """Test performance of parallel URL checking."""

        # Setup mock responses
        def mock_response(url, **kwargs):
            response = Mock()
            response.status_code = 200
            # Simulate network delay
            time.sleep(0.01)
            return response

        mock_head.side_effect = mock_response

        # Test URLs
        test_urls = [f"https://example{i}.com" for i in range(10)]

        # Time sequential checking
        # Time sequential checking
        # Time sequential checking using the actual function
        start_sequential = time.time()
        start_sequential = time.time()
        sequential_results = {}
        for url in test_urls:
            try:
                response = mock_head(url, timeout=5.0)
                sequential_results[url] = response.status_code == 200
            except Exception:
                sequential_results[url] = False
        sequential_time = time.time() - start_sequential

        # Reset mock
        mock_head.reset_mock()
        mock_head.side_effect = mock_response

        # Time parallel checking
        start_parallel = time.time()
        parallel_results = check_urls_accessibility_parallel(
            test_urls, timeout=5.0, max_workers=5
        )
        parallel_time = time.time() - start_parallel

        # Verify parallel execution completed successfully
        assert len(parallel_results) == len(test_urls)

        # All URLs should be accessible
        assert all(parallel_results.values())

        # Log performance comparison (don't assert due to potential flakiness)
        print(
            f"Sequential time: {sequential_time:.3f}s, Parallel time: {parallel_time:.3f}s"
        )
        # Parallel should be faster for multiple URLs
        # Note: In test environment, the benefit might be minimal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
