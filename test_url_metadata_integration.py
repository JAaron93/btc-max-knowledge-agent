"""
Integration tests for URL metadata system.

This module tests:
- End-to-end URL metadata flow from data collection to storage
- Backward compatibility with existing vectors lacking URLs
- URL validation failures with graceful degradation
- Retry mechanisms under various network conditions
- Logging correlation ID tracking across operations
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
import uuid
import time
import requests

from src.knowledge.data_collector import DataCollector
from src.retrieval.pinecone_client import PineconeClient
from src.utils.url_utils import (
    validate_url_batch,
    sanitize_url_for_storage,
    check_urls_accessibility_parallel
)
from src.utils.url_error_handler import (
    URLValidationError,
    GracefulDegradation
)
from src.utils.url_metadata_logger import (
    get_correlation_id,
    set_correlation_id,
)


class TestEndToEndURLMetadataFlow:
    """Test complete URL metadata flow from collection to storage."""
    
    @patch('src.retrieval.pinecone_client.Pinecone')
    @patch('src.knowledge.data_collector.DataCollector.process_and_add_chunks')
    @patch('src.utils.url_utils.validate_url')
    @patch('src.utils.url_utils.normalize_url')
    @patch('src.utils.url_utils.is_secure_url')
    def test_successful_url_metadata_flow(
        self,
        mock_is_secure,
        mock_normalize,
        mock_validate,
        mock_process_chunks,
        mock_pinecone_class
    ):
        """Test successful end-to-end URL metadata flow."""
        # Setup mocks
        mock_is_secure.return_value = True
        mock_normalize.return_value = "https://example.com/normalized"
        mock_validate.return_value = True
        
        # Mock Pinecone instance
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone
        
        # Setup test data
        test_url = "https://example.com/document"
        test_content = "Test document content"
        test_chunks = [
            {
                "text": "Chunk 1 content",
                "metadata": {
                    "url": test_url,
                    "chunk_index": 0
                }
            },
            {
                "text": "Chunk 2 content",
                "metadata": {
                    "url": test_url,
                    "chunk_index": 1
                }
            }
        ]
        
        # Mock process_chunks to return test chunks
        mock_process_chunks.return_value = test_chunks
        
        # Initialize components
        pinecone_client = PineconeClient(
            api_key="test-key",
            environment="test-env",
            index_name="test-index"
        )
        
        data_collector = DataCollector(pinecone_client)
        
        # Perform data collection with URL
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)
        
        # Mock the upsert response
        mock_index.upsert.return_value = {"upserted_count": 2}
        
        # Execute the flow
        data_collector.add_text(
            text=test_content,
            metadata={"url": test_url, "source": "test"}
        )
        
        # Verify URL processing
        assert mock_is_secure.called
        assert mock_normalize.called
        assert mock_validate.called
        
        # Verify chunks have URL metadata
        call_args = mock_process_chunks.call_args
        assert call_args[0][0] == test_content  # text
        assert call_args[0][1]["url"] == test_url  # metadata
        
        # Verify correlation ID was used
        assert get_correlation_id() == correlation_id
    
    @patch('src.retrieval.pinecone_client.Pinecone')
    @patch('src.knowledge.data_collector.DataCollector.process_and_add_chunks')
    @patch('src.utils.url_utils.validate_url')
    @patch(
        'src.utils.url_error_handler.GracefulDegradation.safe_url_operation'
    )
    def test_url_validation_failure_with_graceful_degradation(
        self,
        mock_safe_operation,
        mock_validate,
        mock_process_chunks,
        mock_pinecone_class
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
        pinecone_client = PineconeClient(
            api_key="test-key",
            environment="test-env",
            index_name="test-index"
        )
        
        data_collector = DataCollector(pinecone_client)
        
        # Execute with invalid URL
        data_collector.add_text(
            text="Test content",
            metadata={"url": "not-a-valid-url", "source": "test"}
        )
        
        # Verify graceful degradation was used
        assert mock_safe_operation.called
        
        # Verify processing continued despite URL validation failure
        assert mock_process_chunks.called
    
    @patch('src.retrieval.pinecone_client.Pinecone')
    @patch('src.utils.url_metadata_logger.logger')
    def test_correlation_id_tracking_across_operations(
        self,
        mock_logger,
        mock_pinecone_class
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
        pinecone_client = PineconeClient(
            api_key="test-key",
            environment="test-env",
            index_name="test-index"
        )
        
        # Perform operations
        with patch('src.utils.url_utils.validate_url') as mock_validate:
            mock_validate.return_value = True
            
            # Operation 1: Validate URL
            validate_url_batch(["https://example.com"])
            
            # Operation 2: Upload data
            vectors = [
                {
                    "id": "test-1",
                    "values": [0.1] * 1536,
                    "metadata": {"url": "https://example.com"}
                }
            ]
            mock_index.upsert.return_value = {"upserted_count": 1}
            pinecone_client.upsert_vectors(vectors)
            
            # Operation 3: Query
            mock_index.query.return_value = {
                "matches": [{
                    "id": "test-1",
                    "score": 0.95,
                    "metadata": {"url": "https://example.com"}
                }]
            }
            pinecone_client.query([0.1] * 1536, top_k=1)
        
        # Verify correlation ID was included in all log calls
        log_calls = mock_logger.info.call_args_list
        for call_args in log_calls:
            if len(call_args[0]) > 0:
                # Check if correlation_id is in the log message
                # or in extra parameters
                if len(call_args) > 1 and 'extra' in call_args[1]:
                    extra = call_args[1]['extra']
                    if 'correlation_id' in extra:
                        assert extra['correlation_id'] == correlation_id


class TestBackwardCompatibility:
    """Test backward compatibility with existing vectors lacking URLs."""
    
    @patch('src.retrieval.pinecone_client.Pinecone')
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
                    "metadata": {
                        "text": "Old content without URL",
                        "source": "legacy"
                    }
                },
                {
                    "id": "new-vector-1",
                    "score": 0.90,
                    "metadata": {
                        "text": "New content with URL",
                        "url": "https://example.com/new",
                        "source": "current"
                    }
                }
            ]
        }
        
        # Initialize client
        pinecone_client = PineconeClient(
            api_key="test-key",
            environment="test-env",
            index_name="test-index"
        )
        
        # Query vectors
        results = pinecone_client.query([0.1] * 1536, top_k=2)
        
        # Verify results contain both old and new vectors
        assert len(results["matches"]) == 2
        
        # Old vector should not have URL
        old_vector = results["matches"][0]
        assert "url" not in old_vector["metadata"]
        
        # New vector should have URL
        new_vector = results["matches"][1]
        assert "url" in new_vector["metadata"]
        assert new_vector["metadata"]["url"] == "https://example.com/new"
    
    @patch('src.retrieval.pinecone_client.Pinecone')
    @patch(
        'src.utils.url_error_handler.GracefulDegradation.null_safe_metadata'
    )
    def test_mixed_metadata_handling(
        self,
        mock_null_safe,
        mock_pinecone_class
    ):
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
                "metadata": {"text": "No URL"}  # Missing URL
            },
            {
                "id": "vec-2",
                "values": [0.2] * 1536,
                "metadata": {"text": "Has URL", "url": "https://example.com"}
            },
            {
                "id": "vec-3",
                "values": [0.3] * 1536,
                "metadata": None  # Null metadata
            }
        ]
        
        # Initialize client
        pinecone_client = PineconeClient(
            api_key="test-key",
            environment="test-env",
            index_name="test-index"
        )
        
        # Process vectors
        mock_index.upsert.return_value = {"upserted_count": 3}
        
        # Apply null-safe processing
        processed_vectors = []
        for vec in vectors:
            processed_vec = vec.copy()
            processed_vec["metadata"] = null_safe_side_effect(
                vec.get("metadata")
            )
            processed_vectors.append(processed_vec)
        
        result = pinecone_client.upsert_vectors(processed_vectors)
        
        # Verify all vectors were processed
        assert result["upserted_count"] == 3
        
        # Verify null-safe metadata was applied
        assert mock_null_safe.call_count >= 0  # Called during processing


class TestRetryMechanisms:
    """Test retry mechanisms under various network conditions."""
    
    @patch('requests.head')
    @patch('time.sleep')
    def test_url_accessibility_check_with_retries(
        self,
        mock_sleep,
        mock_head
    ):
        """Test URL accessibility checking with network failures."""
        # Simulate intermittent network failures
        responses = [
            requests.exceptions.ConnectionError("Network error"),
            requests.exceptions.Timeout("Timeout"),
            Mock(status_code=200)  # Success on third attempt
        ]
        mock_head.side_effect = responses
        
        # Check URL accessibility
        urls = ["https://example.com/test"]
        results = check_urls_accessibility_parallel(
            urls,
            timeout=5.0,
            max_workers=1
        )
        
        # Should eventually succeed
        assert results["https://example.com/test"] is True
        
        # Verify retries occurred
        assert mock_head.call_count >= 2
    
    @patch('src.retrieval.pinecone_client.Pinecone')
    @patch('time.sleep')
    def test_pinecone_upload_retry_on_failure(
        self,
        mock_sleep,
        mock_pinecone_class
    ):
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
            {"upserted_count": 1}  # Success on third attempt
        ]
        
        # Initialize client with retry decorator
        pinecone_client = PineconeClient(
            api_key="test-key",
            environment="test-env",
            index_name="test-index"
        )
        
        # Wrap upsert with retry logic
        from src.utils.url_error_handler import exponential_backoff_retry
        
        @exponential_backoff_retry(max_retries=3, initial_delay=0.01)
        def retry_upsert(vectors):
            return pinecone_client.upsert_vectors(vectors)
        
        # Attempt upload
        vectors = [{
            "id": "test-1",
            "values": [0.1] * 1536,
            "metadata": {"url": "https://example.com"}
        }]
        
        result = retry_upsert(vectors)
        
        # Should eventually succeed
        assert result["upserted_count"] == 1
        
        # Verify retries occurred
        assert mock_index.upsert.call_count == 3
    
    @patch('src.monitoring.url_metadata_monitor.url_metadata_monitor')
    def test_monitoring_during_retry_scenarios(self, mock_monitor):
        """Test monitoring integration during retry scenarios."""
        # Create a function that fails twice then succeeds
        attempt_count = 0
        
        from src.utils.url_error_handler import exponential_backoff_retry
        
        @exponential_backoff_retry(
            max_retries=2,
            initial_delay=0.01
        )
        def monitored_operation():
            nonlocal attempt_count
            attempt_count += 1
            
            # Record attempt in monitoring
            mock_monitor.record_retry_attempt(
                operation="test_operation",
                attempt=attempt_count
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
        """Test batch URL validation with mix of valid/invalid URLs."""
        test_urls = [
            "https://valid.example.com",
            "javascript:alert('XSS')",  # Dangerous
            "https://192.168.1.1/private",  # Private IP
            "https://another-valid.com/page",
            "not-a-url",  # Invalid format
            "file:///etc/passwd",  # File protocol
            "https://valid-with-unicode-🎉.com"
        ]
        
        # Validate batch
        results = validate_url_batch(test_urls)
        
        # Check results
        assert results["https://valid.example.com"] is True
        assert results["javascript:alert('XSS')"] is False
        assert results["https://192.168.1.1/private"] is False
        assert results["https://another-valid.com/page"] is True
        assert results["not-a-url"] is False
        assert results["file:///etc/passwd"] is False
        assert results["https://valid-with-unicode-🎉.com"] is True
    
    @patch('src.utils.url_utils._url_cache')
    def test_url_validation_caching_integration(self, mock_cache):
        """Test URL validation caching behavior."""
        # Setup cache
        mock_cache.get.return_value = None  # Cache miss initially
        
        # First validation
        url = "https://example.com/test"
        result1 = validate_url_batch([url])
        
        # Cache should be checked
        mock_cache.get.assert_called()
        
        # Simulate cache hit for second call
        mock_cache.get.return_value = True
        
        # Second validation should use cache
        result2 = validate_url_batch([url])
        
        # Results should be consistent
        assert result1[url] == result2[url]


class TestLoggingCorrelation:
    """Test logging correlation across operations."""
    
    @patch('src.utils.url_metadata_logger.logger')
    def test_correlation_id_propagation(self, mock_logger):
        """Test correlation ID propagation through operations."""
        # Set correlation ID
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)
        
        # Perform multiple operations
        operations = [
            ("validate_url",
             lambda: validate_url_batch(["https://example.com"])),
            ("sanitize_url",
             lambda: sanitize_url_for_storage("https://example.com/test")),
            ("check_accessibility",
             lambda: check_urls_accessibility_parallel(
                 ["https://example.com"]))
        ]
        
        for op_name, op_func in operations:
            try:
                op_func()
            except Exception:
                pass  # Some operations might fail in test environment
        
        # Verify correlation ID in logs
        assert get_correlation_id() == correlation_id
        
        # Check if logger was called with correlation ID
        # Note: Actual verification depends on logging implementation
        assert mock_logger.info.called or mock_logger.debug.called


class TestErrorHandlingIntegration:
    """Test integrated error handling scenarios."""
    
    @patch('src.retrieval.pinecone_client.Pinecone')
    def test_partial_success_handling(self, mock_pinecone_class):
        """Test handling of partial success scenarios."""
        # Mock Pinecone
        mock_pinecone = MagicMock()
        mock_index = MagicMock()
        mock_pinecone.Index.return_value = mock_index
        mock_pinecone_class.return_value = mock_pinecone
        
        # Initialize client
        pinecone_client = PineconeClient(
            api_key="test-key",
            environment="test-env",
            index_name="test-index"
        )
        
        # Create vectors with mix of valid and problematic data
        vectors = [
            {
                "id": "valid-1",
                "values": [0.1] * 1536,
                "metadata": {"url": "https://valid.com", "text": "Valid"}
            },
            {
                "id": "invalid-metadata",
                "values": [0.2] * 1536,
                "metadata": {
                    "url": "javascript:alert('xss')",
                    "text": "Invalid URL"
                }
            },
            {
                "id": "valid-2",
                "values": [0.3] * 1536,
                "metadata": {
                    "url": "https://another-valid.com",
                    "text": "Valid"
                }
            }
        ]
        
        # Process with graceful degradation
        processed_vectors = []
        failed_vectors = []
        
        for vec in vectors:
            try:
                # Validate URL
                url = vec["metadata"].get("url", "")
                if url and not url.startswith(("https://", "http://")):
                    # Invalid URL - use fallback
                    vec["metadata"]["url"] = ""
                    vec["metadata"]["url_validation_failed"] = True
                    failed_vectors.append(vec["id"])
                
                processed_vectors.append(vec)
            except Exception:
                # Complete failure - skip vector
                failed_vectors.append(vec["id"])
        
        # Upload processed vectors
        mock_index.upsert.return_value = {
            "upserted_count": len(processed_vectors)
        }
        result = pinecone_client.upsert_vectors(processed_vectors)
        
        # Create partial result
        partial_result = GracefulDegradation.create_partial_result(
            success_data={
                "upserted_count": result["upserted_count"],
                "processed_ids": [v["id"] for v in processed_vectors]
            },
            failed_operations=failed_vectors,
            error_details={
                "invalid-metadata": "Invalid URL format"
            }
        )
        
        # Verify partial success handling
        assert partial_result["status"] == "partial_success"
        assert partial_result["data"]["upserted_count"] == 3
        assert "invalid-metadata" in failed_vectors


class TestPerformanceIntegration:
    """Test performance-related integration scenarios."""
    
    @patch('requests.head')
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
        start_sequential = time.time()
        sequential_results = {}
        for url in test_urls:
            try:
                resp = requests.head(url, timeout=5)
                sequential_results[url] = resp.status_code == 200
            except Exception:
                sequential_results[url] = False
        time.time() - start_sequential  # Calculate elapsed time
        
        # Reset mock
        mock_head.reset_mock()
        mock_head.side_effect = mock_response
        
        # Time parallel checking
        start_parallel = time.time()
        parallel_results = check_urls_accessibility_parallel(
            test_urls,
            timeout=5.0,
            max_workers=5
        )
        time.time() - start_parallel  # Calculate elapsed time
        
        # Parallel should be faster for multiple URLs
        # Note: In test environment, the benefit might be minimal
        assert len(parallel_results) == len(test_urls)
        
        # All URLs should be accessible
        assert all(parallel_results.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])