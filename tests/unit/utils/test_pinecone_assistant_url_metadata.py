#!/usr/bin/env python3
"""
Test script to verify URL metadata handling in PineconeAssistantAgent
"""

import os
import unittest
from unittest.mock import Mock, patch

import pytest

# Import from the package using absolute import
# NOTE: setup_src_path() is now called once in conftest.py to avoid redundant sys.path modifications
from agents.pinecone_assistant_agent import PineconeAssistantAgent
from btc_max_knowledge_agent.utils.url_error_handler import RetryExhaustedError


class TestPineconeAssistantURLMetadata(unittest.TestCase):
    """Test class for PineconeAssistantAgent URL metadata handling"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock the config and environment variables
        self.config_patcher = patch("agents.pinecone_assistant_agent.Config")
        self.mock_config = self.config_patcher.start()
        self.mock_config.PINECONE_API_KEY = "test-api-key"

        self.env_patcher = patch.dict(
            os.environ, {"PINECONE_ASSISTANT_HOST": "https://test-host.pinecone.io"}
        )
        self.env_patcher.start()

        self.agent = PineconeAssistantAgent()

    def tearDown(self):
        """Clean up after tests"""
        self.config_patcher.stop()
        self.env_patcher.stop()

    # Test data constants
    VALID_URLS = [
        "https://example.com",
        "http://example.com",
        "https://subdomain.example.com",
        "https://example.com/path",
        "https://example.com/path?query=value",
    ]

    URL_PROTOCOL_TEST_CASES = [
        ("example.com", "https://example.com"),
        ("subdomain.example.com", "https://subdomain.example.com"),
        ("example.com/path", "https://example.com/path"),
    ]

    INVALID_URLS = [
        None,
        "",
        "   ",
        "not-a-url",
        "http://",
        "https://",
        "ftp://example.com",  # Wrong protocol
        "invalid-domain",
        "http://localhost",  # No TLD
        123,  # Not a string
        [],  # Not a string
    ]

    def test_validate_and_sanitize_url_valid_urls(self):
        """Test URL validation with valid URLs"""
        for url in self.VALID_URLS:
            result = self.agent._validate_and_sanitize_url(url)
            self.assertEqual(result, url, f"Valid URL {url} should be returned as-is")

    def test_validate_and_sanitize_url_missing_protocol(self):
        """Test URL validation with missing protocol"""
        for input_url, expected in self.URL_PROTOCOL_TEST_CASES:
            result = self.agent._validate_and_sanitize_url(input_url)
            self.assertEqual(
                result, expected, f"URL {input_url} should be sanitized to {expected}"
            )

    def test_validate_and_sanitize_url_invalid_urls(self):
        """Test URL validation with invalid URLs"""
        for url in self.INVALID_URLS:
            result = self.agent._validate_and_sanitize_url(url)
            self.assertIsNone(result, f"Invalid URL {url} should return None")

    @patch("agents.pinecone_assistant_agent.requests.post")
    def test_upload_documents_with_url_metadata(self, mock_post):
        """Test document upload with URL metadata"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        # Test documents with various URL scenarios
        documents = [
            {
                "id": "doc1",
                "title": "Test Document 1",
                "content": "This is test content 1",
                "source": "Test Source 1",
                "category": "test",
                "url": "https://example.com/doc1",
                "published": "2024-01-01",
            },
            {
                "id": "doc2",
                "title": "Test Document 2",
                "content": "This is test content 2",
                "source": "Test Source 2",
                "category": "test",
                "url": "example.com/doc2",  # Missing protocol
                "published": "2024-01-02",
            },
            {
                "id": "doc3",
                "title": "Test Document 3",
                "content": "This is test content 3",
                "source": "Test Source 3",
                "category": "test",
                "url": "invalid-url",  # Invalid URL
                "published": "2024-01-03",
            },
            {
                "id": "doc4",
                "title": "Test Document 4",
                "content": "This is test content 4",
                "source": "Test Source 4",
                "category": "test",
                # No URL field
            },
        ]

        # Call upload_documents
        result = self.agent.upload_documents("test-assistant-id", documents)

        # Verify the method returned True
        self.assertTrue(result)

        # Verify the request was made
        mock_post.assert_called_once()

        # Get the request data
        call_args = mock_post.call_args
        request_data = call_args[1]["json"]
        uploaded_docs = request_data["documents"]

        # Verify first document has correct URL
        self.assertEqual(
            uploaded_docs[0]["metadata"]["url"], "https://example.com/doc1"
        )
        self.assertEqual(uploaded_docs[0]["metadata"]["published"], "2024-01-01")

        # Verify second document has sanitized URL
        self.assertEqual(
            uploaded_docs[1]["metadata"]["url"], "https://example.com/doc2"
        )
        self.assertEqual(uploaded_docs[1]["metadata"]["published"], "2024-01-02")

        # Verify third document has empty URL (invalid URL)
        self.assertEqual(uploaded_docs[2]["metadata"]["url"], "")
        self.assertEqual(uploaded_docs[2]["metadata"]["published"], "2024-01-03")

        # Verify fourth document has empty URL and published fields
        self.assertEqual(uploaded_docs[3]["metadata"]["url"], "")
        self.assertEqual(uploaded_docs[3]["metadata"]["published"], "")

        # Verify all documents have the required metadata fields
        for doc in uploaded_docs:
            self.assertIn("url", doc["metadata"])
            self.assertIn("published", doc["metadata"])
            self.assertIn("title", doc["metadata"])
            self.assertIn("source", doc["metadata"])
            self.assertIn("category", doc["metadata"])

    @patch("agents.pinecone_assistant_agent.requests.post")
    def test_upload_documents_batch_processing(self, mock_post):
        """Test that large document sets are processed in batches"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        # Create 75 documents (should be split into 2 batches of 50 and 25)
        documents = []
        for i in range(75):
            documents.append(
                {
                    "id": f"doc{i}",
                    "title": f"Test Document {i}",
                    "content": f"This is test content {i}",
                    "source": f"Test Source {i}",
                    "category": "test",
                    "url": f"https://example.com/doc{i}",
                }
            )

        # Call upload_documents
        result = self.agent.upload_documents("test-assistant-id", documents)

        # Verify the method returned True
        self.assertTrue(result)

        # Verify two requests were made (2 batches)
        self.assertEqual(mock_post.call_count, 2)

        # Verify first batch has 50 documents
        first_call_data = mock_post.call_args_list[0][1]["json"]
        self.assertEqual(len(first_call_data["documents"]), 50)

        # Verify second batch has 25 documents
        second_call_data = mock_post.call_args_list[1][1]["json"]
        self.assertEqual(len(second_call_data["documents"]), 25)

    def test_format_sources_with_urls(self):
        """Test formatting of sources with URL information"""
        # Mock citations from Pinecone Assistant
        citations = [
            {
                "id": "doc1",
                "text": "This is the content from document 1",
                "score": 0.95,
                "metadata": {
                    "title": "Test Document 1",
                    "source": "Test Source 1",
                    "category": "test",
                    "url": "https://example.com/doc1",
                    "published": "2024-01-01",
                },
            },
            {
                "id": "doc2",
                "text": "This is the content from document 2",
                "score": 0.85,
                "metadata": {
                    "title": "Test Document 2",
                    "source": "Test Source 2",
                    "category": "test",
                    "url": "",  # Empty URL
                    "published": "",
                },
            },
        ]

        # Call the formatting method
        formatted_sources = self.agent._format_sources_with_urls(citations)

        # Verify the results
        self.assertEqual(len(formatted_sources), 2)

        # Check first source
        first_source = formatted_sources[0]
        self.assertEqual(first_source["id"], "doc1")
        self.assertEqual(first_source["title"], "Test Document 1")
        self.assertEqual(first_source["url"], "https://example.com/doc1")
        self.assertEqual(first_source["published"], "2024-01-01")
        self.assertEqual(first_source["score"], 0.95)
        self.assertEqual(first_source["content"], "This is the content from document 1")

        # Check second source (empty URL)
        second_source = formatted_sources[1]
        self.assertEqual(second_source["id"], "doc2")
        self.assertEqual(second_source["title"], "Test Document 2")
        self.assertEqual(second_source["url"], "")
        self.assertEqual(second_source["published"], "")
        self.assertEqual(second_source["score"], 0.85)
        self.assertEqual(
            second_source["content"], "This is the content from document 2"
        )

    @patch("agents.pinecone_assistant_agent.requests.post")
    def test_query_assistant_with_url_metadata(self, mock_post):
        """Test querying assistant and receiving URL metadata in response"""
        # Mock successful response with citations
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "This is the assistant response about Bitcoin.",
            "citations": [
                {
                    "id": "doc1",
                    "text": "Bitcoin is a peer-to-peer electronic cash system.",
                    "score": 0.95,
                    "metadata": {
                        "title": "Bitcoin Whitepaper",
                        "source": "bitcoin.org",
                        "category": "fundamentals",
                        "url": "https://bitcoin.org/bitcoin.pdf",
                        "published": "2008-10-31",
                    },
                },
                {
                    "id": "doc2",
                    "text": "Lightning Network enables fast Bitcoin transactions.",
                    "score": 0.88,
                    "metadata": {
                        "title": "Lightning Network Paper",
                        "source": "lightning.network",
                        "category": "layer2",
                        "url": "https://lightning.network/lightning-network-paper.pdf",
                        "published": "2016-01-14",
                    },
                },
            ],
            "metadata": {"query_time": 0.5},
        }
        mock_post.return_value = mock_response

        # Call query_assistant
        result = self.agent.query_assistant("test-assistant-id", "What is Bitcoin?")

        # Verify the response structure
        self.assertIn("answer", result)
        self.assertIn("sources", result)
        self.assertIn("metadata", result)

        # Verify the answer
        self.assertEqual(
            result["answer"], "This is the assistant response about Bitcoin."
        )

        # Verify the sources include URL metadata
        sources = result["sources"]
        self.assertEqual(len(sources), 2)

        # Check first source
        first_source = sources[0]
        self.assertEqual(first_source["id"], "doc1")
        self.assertEqual(first_source["title"], "Bitcoin Whitepaper")
        self.assertEqual(first_source["url"], "https://bitcoin.org/bitcoin.pdf")
        self.assertEqual(first_source["published"], "2008-10-31")
        self.assertEqual(first_source["score"], 0.95)

        # Check second source
        second_source = sources[1]
        self.assertEqual(second_source["id"], "doc2")
        self.assertEqual(second_source["title"], "Lightning Network Paper")
        self.assertEqual(
            second_source["url"],
            "https://lightning.network/lightning-network-paper.pdf",
        )
        self.assertEqual(second_source["published"], "2016-01-14")
        self.assertEqual(second_source["score"], 0.88)

        # Verify all sources have required fields
        for source in sources:
            self.assertIn("url", source)
            self.assertIn("published", source)
            self.assertIn("title", source)
            self.assertIn("source", source)
            self.assertIn("category", source)
            self.assertIn("content", source)
            self.assertIn("score", source)

    @patch("agents.pinecone_assistant_agent.requests.post")
    def test_query_assistant_handles_missing_citations(self, mock_post):
        """Test querying assistant when response has no citations"""
        # Mock response without citations
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "This is a response without citations.",
            "metadata": {"query_time": 0.3},
        }
        mock_post.return_value = mock_response

        # Call query_assistant
        result = self.agent.query_assistant("test-assistant-id", "What is Bitcoin?")

        # Verify the response structure
        self.assertIn("answer", result)
        self.assertIn("sources", result)
        self.assertIn("metadata", result)

        # Verify empty sources list
        self.assertEqual(len(result["sources"]), 0)
        self.assertEqual(result["answer"], "This is a response without citations.")

    @patch("agents.pinecone_assistant_agent.requests.post")
    def test_upload_documents_handles_request_failure(self, mock_post):
        """Test upload_documents handles API request failures gracefully"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        # Test documents
        documents = [
            {
                "id": "doc1",
                "title": "Test Document",
                "content": "Test content",
                "source": "Test Source",
                "category": "test",
                "url": "https://example.com",
            }
        ]

        # Call upload_documents and expect RetryExhaustedError
        with self.assertRaises(RetryExhaustedError):
            self.agent.upload_documents("test-assistant-id", documents)

    @patch("agents.pinecone_assistant_agent.requests.post")
    def test_query_assistant_handles_request_failure(self, mock_post):
        """Test query_assistant handles API request failures gracefully"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        # Call query_assistant
        result = self.agent.query_assistant("test-assistant-id", "What is Bitcoin?")

        # Verify error response
        self.assertIn("answer", result)
        self.assertIn("sources", result)
        self.assertEqual(result["sources"], [])
        self.assertIn("Sorry, I encountered an error", result["answer"])


def main():
    """Run the tests"""
    print("🧪 Testing Pinecone Assistant URL Metadata Functionality")
    print("=" * 60)

    # Run pytest
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    main()
