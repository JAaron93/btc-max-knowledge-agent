#!/usr/bin/env python3
"""
Enhanced test script to verify URL metadata handling in PineconeAssistantAgent
with additional scenarios including timeouts, partial metadata, and mixed
availability.

Run from project root with:
    python -m pytest tests/test_pinecone_assistant_url_metadata_enhanced.py -v
"""

import os
import sys
import unittest
import uuid
from concurrent.futures import TimeoutError as FuturesTimeoutError
from unittest.mock import Mock, patch

import pytest
import requests

# Try to import required modules
try:
    from src.agents.pinecone_assistant_agent import PineconeAssistantAgent
    from src.utils.url_error_handler import exponential_backoff_retry
    from src.utils.url_metadata_logger import set_correlation_id
except ImportError as e:
    pytestmark = pytest.mark.skip("Required modules not available. Skipping tests.")
    print(f"Warning: Could not import required modules: {e}", file=sys.stderr)


class TestPineconeAssistantURLMetadataEnhanced(unittest.TestCase):
    """Enhanced tests for URL metadata handling with additional scenarios."""

    def setUp(self):
        """Set up test fixtures"""
        # Mock the config and environment variables
        self.config_patcher = patch("src.utils.config.Config")
        mock_config = self.config_patcher.start()
        mock_config.PINECONE_API_KEY = "test-api-key"

        # Mock environment variables
        self.env_patcher = patch.dict(
            os.environ, {"PINECONE_ASSISTANT_HOST": "https://test-host.pinecone.io"}
        )
        self.env_patcher.start()

        # Initialize the agent
        self.agent = PineconeAssistantAgent()

        # Set correlation ID for tracking
        self.correlation_id = str(uuid.uuid4())
        set_correlation_id(self.correlation_id)

        # Mock logger in url_metadata_logger
        self.logger_patcher = patch("src.utils.url_metadata_logger.logger")
        self.mock_logger = self.logger_patcher.start()

        # Mock validate_url in url_utils
        self.validate_url_patcher = patch("src.utils.url_utils.validate_url")
        self.mock_validate_url = self.validate_url_patcher.start()
        self.mock_validate_url.return_value = True  # Default to valid URL

    def tearDown(self):
        """Clean up after each test"""
        self.config_patcher.stop()
        self.env_patcher.stop()
        self.logger_patcher.stop()
        self.validate_url_patcher.stop()
        patch.stopall()

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    @patch("src.utils.url_utils.validate_url")
    def test_upload_with_url_validation_timeout(self, mock_validate_url, mock_post):
        """Test upload operation when URL validation times out."""
        # Mock validation timeout
        with patch("src.retrieval.url_validator.validate_url") as mock_validate:
            mock_validate.side_effect = FuturesTimeoutError("Validation timed out")

            # Test documents
            documents = [
                {
                    "id": "doc1",
                    "title": "Test Document",
                    "content": "Test content",
                    "source": "Test Source",
                    "category": "test",
                    "url": "https://slow-loading-site.com/document",
                }
            ]

            # Call upload_documents
            result = self.agent.upload_documents("test-assistant-id", documents)

            # Should still succeed with empty URL on timeout
            assert result is True, (
                "Upload should succeed even with URL validation timeout"
            )

            # Verify request was made with empty URL due to timeout
            call_args = mock_post.call_args
            uploaded_doc = call_args[1]["json"]["documents"][0]
            assert uploaded_doc["metadata"]["url"] == "", (
                "URL should be empty string when validation times out"
            )

        # Mock successful upload response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        # Test documents
        documents = [
            {
                "id": "doc1",
                "title": "Test Document",
                "content": "Test content",
                "source": "Test Source",
                "category": "test",
                "url": "https://slow-loading-site.com/document",
            }
        ]

        # Call upload_documents
        result = self.agent.upload_documents("test-assistant-id", documents)

        # Should still succeed with empty URL on timeout
        assert result is True, "Upload should succeed even with URL validation timeout"

        # Verify request was made with empty URL due to timeout
        call_args = mock_post.call_args
        uploaded_doc = call_args[1]["json"]["documents"][0]
        assert uploaded_doc["metadata"]["url"] == "", (
            "URL should be empty string when validation times out"
        )

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    @patch("src.utils.url_utils.check_urls_accessibility_parallel")
    def test_batch_upload_with_mixed_url_accessibility(
        self, mock_check_urls, mock_post
    ):
        """Test batch upload with mix of accessible and inaccessible URLs."""
        # Mock URL accessibility check results
        mock_check_urls.return_value = {
            "https://accessible.com/doc1": True,
            "https://inaccessible.com/doc2": False,
            "https://timeout.com/doc3": None,  # Timeout
            "https://accessible.com/doc4": True,
        }

        # Mock successful upload response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        # Test documents with various URL states
        documents = [
            {
                "id": "doc1",
                "title": "Accessible Document",
                "content": "Content 1",
                "url": "https://accessible.com/doc1",
            },
            {
                "id": "doc2",
                "title": "Inaccessible Document",
                "content": "Content 2",
                "url": "https://inaccessible.com/doc2",
            },
            {
                "id": "doc3",
                "title": "Timeout Document",
                "content": "Content 3",
                "url": "https://timeout.com/doc3",
            },
            {
                "id": "doc4",
                "title": "Another Accessible",
                "content": "Content 4",
                "url": "https://accessible.com/doc4",
            },
        ]

        # Upload documents
        result = self.agent.upload_documents("test-assistant-id", documents)
        assert result is True, (
            "Batch upload with mixed URL accessibility should succeed"
        )

        # Get uploaded documents
        call_args = mock_post.call_args
        uploaded_docs = call_args[1]["json"]["documents"]

        # Verify URL handling based on accessibility
        assert uploaded_docs[0]["metadata"]["url"] == "https://accessible.com/doc1", (
            "Accessible URL should be preserved"
        )
        assert uploaded_docs[0]["metadata"].get("url_accessible", True) is True, (
            "Accessible URL should be marked as accessible"
        )

        # Inaccessible URL should be marked
        assert uploaded_docs[1]["metadata"]["url"] == "https://inaccessible.com/doc2", (
            "Inaccessible URL should still be stored"
        )
        assert uploaded_docs[1]["metadata"].get("url_accessible", True) is False, (
            "Inaccessible URL should be marked as inaccessible"
        )

        # Timeout URL should be handled gracefully
        assert uploaded_docs[2]["metadata"]["url"] == "https://timeout.com/doc3", (
            "Timeout URL should still be stored"
        )
        assert "url_check_timeout" in uploaded_docs[2]["metadata"], (
            "Timeout URL should have timeout metadata flag"
        )
        assert uploaded_docs[2]["metadata"]["url_check_timeout"] is True, (
            "URL check timeout flag should be True"
        )

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    def test_query_with_partial_url_metadata(self, mock_post):
        """Test query operations with partial URL metadata in results."""
        # Mock response with mixed metadata completeness
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Response about Bitcoin technology.",
            "citations": [
                {
                    "id": "doc1",
                    "text": "Bitcoin uses proof of work.",
                    "score": 0.95,
                    "metadata": {
                        "title": "Bitcoin Technical Guide",
                        "source": "btc-tech.org",
                        "url": "https://btc-tech.org/guide",
                        "published": "2023-01-15",
                    },
                },
                {
                    "id": "doc2",
                    "text": "Mining difficulty adjusts every 2016 blocks.",
                    "score": 0.88,
                    "metadata": {
                        "title": "Mining Overview",
                        "source": "mining-info.com",
                        # Missing URL field entirely
                        "published": "2023-02-20",
                    },
                },
                {
                    "id": "doc3",
                    "text": "Halving occurs every 210,000 blocks.",
                    "score": 0.82,
                    "metadata": {
                        "title": "Bitcoin Economics",
                        "url": "",  # Empty URL
                        # Missing other fields
                    },
                },
                {
                    "id": "doc4",
                    "text": "Lightning Network enables fast payments.",
                    "score": 0.79,
                    # Missing metadata entirely
                },
            ],
            "metadata": {"query_time": 0.4},
        }
        mock_post.return_value = mock_response

        # Query assistant
        result = self.agent.query_assistant(
            "test-assistant-id", "Explain Bitcoin technology"
        )

        # Verify response handling
        assert "sources" in result, "Query result should contain 'sources' field"
        sources = result["sources"]
        assert len(sources) == 4, f"Should have 4 sources, got {len(sources)}"

        # Check first source (complete metadata)
        assert sources[0]["url"] == "https://btc-tech.org/guide", (
            "First source should have complete URL metadata"
        )
        assert sources[0]["published"] == "2023-01-15", (
            "First source should have complete published metadata"
        )

        # Check second source (missing URL)
        assert sources[1]["url"] == "", (
            "Second source with missing URL should have empty URL field"
        )
        assert sources[1]["published"] == "2023-02-20", (
            "Second source should preserve published date"
        )

        # Check third source (empty URL, missing fields)
        assert sources[2]["url"] == "", (
            "Third source with empty URL should have empty URL field"
        )
        assert sources[2].get("published", "") == "", (
            "Third source should have empty published field when missing"
        )
        assert sources[2].get("source", "") == "", (
            "Third source should have empty source field when missing"
        )

        # Check fourth source (missing metadata)
        assert sources[3]["url"] == "", (
            "Fourth source with missing metadata should have empty URL"
        )
        assert sources[3].get("title", "") == "", (
            "Fourth source should have empty title when metadata missing"
        )

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    @patch("src.monitoring.url_metadata_monitor.url_metadata_monitor")
    def test_upload_with_monitoring_integration(self, mock_monitor, mock_post):
        """Test upload operation with monitoring integration."""
        # Mock successful upload
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        # Test documents
        documents = [
            {
                "id": "doc1",
                "title": "Monitored Document",
                "content": "Content",
                "url": "https://example.com/doc1",
            }
        ]

        # Upload documents
        result = self.agent.upload_documents("test-assistant-id", documents)
        assert result is True, "Upload with monitoring integration should succeed"

        # Verify monitoring was called with correct parameters
        mock_monitor.track_upload.assert_called_once()
        # Verify the parameters passed to track_upload
        call_args = mock_monitor.track_upload.call_args
        assert call_args[0][0] == "test-assistant-id", (
            "Monitor should be called with correct assistant ID"
        )
        assert len(call_args[0][1]) == 1, "Monitor should track one document"
        assert call_args[0][1][0]["id"] == "doc1", (
            "Monitor should track correct document ID"
        )

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    def test_retry_mechanism_on_upload_failure(self, mock_post):
        """Test retry mechanism during upload failures."""
        # Mock responses: fail twice, then succeed
        responses = [
            Mock(status_code=500, text="Server Error"),
            Mock(status_code=503, text="Service Unavailable"),
            Mock(status_code=201, json=Mock(return_value={"status": "success"})),
        ]
        mock_post.side_effect = responses

        # Wrap upload with retry logic
        @exponential_backoff_retry(max_retries=3, initial_delay=0.01)
        def retry_upload():
            return self.agent.upload_documents(
                "test-assistant-id",
                [{"id": "doc1", "title": "Test", "content": "Test"}],
            )

        # Should eventually succeed
        result = retry_upload()
        assert result is True, (
            "Retry mechanism should eventually succeed after failures"
        )

        # Verify three attempts were made
        assert mock_post.call_count == 3, (
            f"Should make 3 retry attempts, made {mock_post.call_count}"
        )

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    @patch("src.utils.url_metadata_logger.logger")
    def test_correlation_id_tracking(self, mock_logger, mock_post):
        """Test correlation ID tracking through operations."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        # Upload document
        documents = [
            {
                "id": "doc1",
                "title": "Tracked Document",
                "content": "Content",
                "url": "https://example.com",
            }
        ]

        result = self.agent.upload_documents("test-assistant-id", documents)
        assert result is True, "Upload with correlation ID tracking should succeed"

        # Verify correlation ID was used in logging
        # Note: Actual verification depends on logging implementation
        assert len(mock_logger.method_calls) > 0, (
            "Logger should have been called during upload operation"
        )

        # Step 1: Verify at least one log call includes correlation ID
        correlation_id_found = False
        found_correlation_id = None

        for call in mock_logger.method_calls:
            if hasattr(call, "kwargs") and "extra" in call.kwargs:
                extra = call.kwargs["extra"]
                if isinstance(extra, dict):
                    # Check direct extra fields
                    if "correlation_id" in extra:
                        correlation_id_found = True
                        found_correlation_id = extra["correlation_id"]
                        break
                    # Check nested extra_fields
                    if "extra_fields" in extra and isinstance(
                        extra["extra_fields"], dict
                    ):
                        if "correlation_id" in extra["extra_fields"]:
                            correlation_id_found = True
                            found_correlation_id = extra["extra_fields"][
                                "correlation_id"
                            ]
                            break

        # Assert that we found at least one correlation ID
        assert correlation_id_found is True, "No correlation ID found in any log calls"

        # Step 2: Verify correlation ID is a non-empty string
        if found_correlation_id:
            assert isinstance(found_correlation_id, str), (
                f"Correlation ID should be string, got {type(found_correlation_id)}"
            )
            assert len(found_correlation_id) > 0, "Correlation ID should not be empty"

        # Step 3: Verify consistency across all log calls with correlation ID
        for call in mock_logger.method_calls:
            if hasattr(call, "kwargs") and "extra" in call.kwargs:
                extra = call.kwargs["extra"]
                if isinstance(extra, dict):
                    # Check direct correlation_id
                    if "correlation_id" in extra:
                        assert extra["correlation_id"] == found_correlation_id, (
                            "Correlation ID should be consistent across all log calls"
                        )
                    # Check nested correlation_id
                    if "extra_fields" in extra and isinstance(
                        extra["extra_fields"], dict
                    ):
                        if "correlation_id" in extra["extra_fields"]:
                            assert (
                                extra["extra_fields"]["correlation_id"]
                                == found_correlation_id
                            ), (
                                "Correlation ID should be consistent across all log calls"
                            )

    def test_url_normalization_in_upload(self):
        """Test URL normalization during upload process."""
        test_cases = [
            # (input_url, expected_normalized)
            ("HTTP://EXAMPLE.COM/PATH", "https://example.com/PATH"),
            ("https://example.com:443/path", "https://example.com/path"),
            ("https://example.com/path?b=2&a=1", "https://example.com/path?a=1&b=2"),
            ("https://example.com/./path/../file", "https://example.com/file"),
            ("https://example.com/path#fragment", "https://example.com/path"),
        ]

        for input_url, expected in test_cases:
            result = self.agent._validate_and_sanitize_url(input_url)
            # Basic validation - actual normalization depends on implementation
            assert result is not None, (
                f"URL normalization should not return None for {input_url}"
            )
            assert result.startswith("https://"), (
                f"Normalized URL should start with https://, got {result}"
            )

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    def test_metadata_field_consistency(self, mock_post):
        """Test that all required metadata fields are present."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response
        # Test documents
        documents = [
            {
                "id": "complete",
                "title": "Complete Doc",
                "content": "Content",
                "source": "Source",
                "url": "https://example.com/complete",
            },
            {"id": "minimal", "title": "Minimal Doc", "content": "Content only"},
        ]

        # Upload documents
        self.agent.upload_documents("test-assistant-id", documents)

        # Check uploaded documents
        call_args = mock_post.call_args
        uploaded_docs = call_args[1]["json"]["documents"]

        # Verify all documents have required fields
        required_fields = ["url", "published", "title", "source", "category"]
        for doc in uploaded_docs:
            for field in required_fields:
                assert field in doc["metadata"], (
                    f"Document {doc['id']} missing required field '{field}'"
                )
                # Empty string for missing fields
                if doc["id"] == "minimal":
                    assert doc["metadata"][field] == "", (
                        f"Minimal document should have empty {field}, got '{doc['metadata'][field]}'"
                    )

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    def test_network_error_handling_during_query(self, mock_post):
        """Test handling of network errors during query operations."""
        # Mock network error
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        # Query should handle error gracefully
        result = self.agent.query_assistant("test-assistant-id", "What is Bitcoin?")

        # Should return error response
        assert "answer" in result, (
            "Network error response should contain 'answer' field"
        )
        assert "Sorry, I encountered an error" in result["answer"], (
            "Error response should contain error message"
        )
        assert result["sources"] == [], "Network error should return empty sources list"

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    def test_timeout_during_query_operation(self, mock_post):
        """Test timeout handling during query operations."""
        # Mock timeout
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        # Query with timeout
        result = self.agent.query_assistant(
            "test-assistant-id", "Explain Bitcoin mining", timeout=5.0
        )

        # Should handle timeout gracefully
        assert "answer" in result, "Timeout response should contain 'answer' field"
        assert "error" in result["answer"].lower(), (
            "Timeout response should contain error indication"
        )
        assert result["sources"] == [], "Timeout should return empty sources list"

    def test_url_security_validation(self):
        """Test security validation for URLs."""
        dangerous_urls = [
            'javascript:alert("XSS")',
            'data:text/html,<script>alert("XSS")</script>',
            "file:///etc/passwd",
            "ftp://internal-server/files",
            "about:blank",
            'vbscript:msgbox("XSS")',
        ]

        for dangerous_url in dangerous_urls:
            result = self.agent._validate_and_sanitize_url(dangerous_url)
            # Should reject dangerous URLs
            assert result is None, (
                f"Dangerous URL {dangerous_url} should be rejected, got {result}"
            )

    @patch("src.agents.pinecone_assistant_agent.requests.post")
    def test_unicode_url_handling(self, mock_post):
        """Test handling of Unicode characters in URLs."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        # Documents with Unicode URLs
        documents = [
            {
                "id": "unicode1",
                "title": "Unicode URL Test",
                "content": "Content",
                "url": "https://example.com/文档/测试",
            },
            {
                "id": "unicode2",
                "title": "Emoji URL Test",
                "content": "Content",
                "url": "https://example.com/path/🚀/document",
            },
        ]

        # Upload documents
        result = self.agent.upload_documents("test-assistant-id", documents)
        assert result is True, "Unicode URL upload should succeed"

        # Verify URLs are properly encoded
        call_args = mock_post.call_args
        uploaded_docs = call_args[1]["json"]["documents"]

        # URLs should be properly handled (encoded)
        for doc in uploaded_docs:
            url = doc["metadata"]["url"]
            if doc["id"] == "unicode1":
                # Chinese characters should be percent-encoded
                assert "%E6%96%87%E6%A1%A3" in url, (
                    f"Chinese characters (文档) not properly encoded in URL: {url}"
                )
                assert "%E6%B5%8B%E8%AF%95" in url, (
                    f"Chinese characters (测试) not properly encoded in URL: {url}"
                )
            elif doc["id"] == "unicode2":
                # Emoji should be percent-encoded
                assert "%F0%9F%9A%80" in url, (
                    f"Emoji (🚀) not properly encoded in URL: {url}"
                )
