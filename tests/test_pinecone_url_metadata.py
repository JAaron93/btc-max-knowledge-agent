#!/usr/bin/env python3
"""
Test script to verify URL metadata handling in PineconeClient
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add the project root to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.retrieval.pinecone_client import PineconeClient


class TestPineconeURLMetadata(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        import os
        
        # Mock environment variables for Config
        test_env_vars = {
            "PINECONE_API_KEY": "test-key",
            "PINECONE_INDEX_NAME": "test-index", 
            "EMBEDDING_DIMENSION": "768",
            "ALLOW_LOCALHOST_URLS": "True",  # Enable localhost URLs for dev/test
        }
        
        # Mock the external dependencies
        with patch("src.retrieval.pinecone_client.Pinecone"), \
             patch.dict(os.environ, test_env_vars, clear=False):
            self.client = PineconeClient()

    def test_validate_and_sanitize_url_valid_urls(self):
        """Test URL validation with valid URLs"""
        # Test valid URLs with expected normalized output
        valid_url_test_cases = [
            ("https://example.com", "https://example.com/"),  # Normalization adds trailing slash
            ("http://example.com", "http://example.com/"),
            ("https://subdomain.example.com", "https://subdomain.example.com/"),
            ("https://example.com/path", "https://example.com/path"),
            ("https://example.com/path?query=value", "https://example.com/path?query=value"),
        ]

        for input_url, expected_url in valid_url_test_cases:
            result = self.client.validate_and_sanitize_url(input_url)
            assert (
                result == expected_url
            ), f"Valid URL {input_url} should be normalized to {expected_url}, got {result}"

    def test_validate_and_sanitize_url_missing_protocol(self):
        """Test URL validation with missing protocol"""
        # Test URLs without protocol
        test_cases = [
            ("example.com", "https://example.com"),
            ("subdomain.example.com", "https://subdomain.example.com"),
            ("example.com/path", "https://example.com/path"),
        ]

        for input_url, expected in test_cases:
            result = self.client.validate_and_sanitize_url(input_url)
            assert (
                result == expected
            ), f"URL {input_url} should be sanitized to {expected}, got {result}"

    def test_validate_and_sanitize_url_invalid_urls(self):
        """Test URL validation with invalid URLs"""
        invalid_urls = [
            None,
            "",
            "   ",
            "not-a-url",
            "http://",
            "https://",
            "ftp://example.com",  # Wrong protocol
            "invalid-domain",
            123,  # Not a string
            [],  # Not a string
        ]

        for url in invalid_urls:
            result = self.client.validate_and_sanitize_url(url)
            assert result is None or result.startswith("https://"), f"Invalid URL {url} should return None or be prefixed with https://, got {result}"

    def test_validate_and_sanitize_url_localhost_allowed(self):
        """Test URL validation with localhost URLs when ALLOW_LOCALHOST_URLS=True"""
        localhost_test_cases = [
            ("http://localhost", "http://localhost/"),  # URL normalization adds trailing slash
            ("https://localhost", "https://localhost/"), 
            ("http://localhost:8080", "http://localhost:8080/"),
            ("https://localhost:3000", "https://localhost:3000/"),
            ("http://localhost/path", "http://localhost/path"),
            ("https://localhost/path?query=value", "https://localhost/path?query=value"),
        ]

        for input_url, expected_url in localhost_test_cases:
            result = self.client.validate_and_sanitize_url(input_url)
            assert result == expected_url, f"Localhost URL {input_url} should be normalized to {expected_url} when ALLOW_LOCALHOST_URLS=True, got {result}"

    def test_upsert_documents_with_url_metadata(self):
        """Test document upsert with URL metadata"""
        # Mock the index
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)

        # Test documents with URLs and embeddings
        documents = [
            {
                "id": "doc1",
                "title": "Test Document 1",
                "content": "This is test content 1",
                "source": "Test Source 1",
                "category": "test",
                "url": "https://example.com/doc1",
                'embedding': [0.1] * mock_config.EMBEDDING_DIMENSION,
            },
            {
                "id": "doc2",
                "title": "Test Document 2",
                "content": "This is test content 2",
                "source": "Test Source 2",
                "category": "test",
                "url": "example.com/doc2",  # Missing protocol
                "embedding": [0.2] * 768,
            },
            {
                "id": "doc3",
                "title": "Test Document 3",
                "content": "This is test content 3",
                "source": "Test Source 3",
                "category": "test",
                "embedding": [0.3] * 768,
                # No URL field
            },
        ]

        # Call upsert_documents
        self.client.upsert_documents(documents)

        # Verify upsert was called
        mock_index.upsert.assert_called_once()

        # Get the vectors that were upserted
        call_args = mock_index.upsert.call_args[1]["vectors"]

        # Verify first document has correct URL
        assert (
            call_args[0]["metadata"]["url"] == "https://example.com/doc1"
        ), "First document URL should be unchanged"

        # Verify second document has sanitized URL
        assert (
            call_args[1]["metadata"]["url"] == "https://example.com/doc2"
        ), "Second document URL should be sanitized with https://"

        # Verify third document has empty URL
        assert (
            call_args[2]["metadata"]["url"] == ""
        ), "Third document without URL field should have empty URL"

        # Verify all documents have the URL field in metadata
        for i, vector in enumerate(call_args):
            assert (
                "url" in vector["metadata"]
            ), f"Document {i} metadata missing 'url' field"

    def test_upsert_documents_with_published_date(self):
        """Test document upsert with published date metadata"""
        # Mock the index
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)

        # Test document with published date
        documents = [
            {
                "id": "doc1",
                "title": "Test Document",
                "content": "This is test content",
                "source": "Test Source",
                "category": "test",
                "url": "https://example.com",
                "published": "2024-01-01",
                "embedding": [0.1] * 768,
            }
        ]

        # Call upsert_documents
        self.client.upsert_documents(documents)

        # Get the vectors that were upserted
        call_args = mock_index.upsert.call_args[1]["vectors"]

        # Verify published date is included
        assert (
            call_args[0]["metadata"]["published"] == "2024-01-01"
        ), "Published date should be preserved in metadata"

    def test_query_similar_returns_url_metadata(self):
        """Test that query_similar returns URL metadata in results"""
        # Mock the index and query results
        mock_index = Mock()
        mock_query_results = {
            "matches": [
                {
                    "id": "doc1",
                    "score": 0.95,
                    "metadata": {
                        "title": "Test Document 1",
                        "source": "Test Source 1",
                        "category": "test",
                        "content": "Test content 1",
                        "url": "https://example.com/doc1",
                        "published": "2024-01-01",
                    },
                },
                {
                    "id": "doc2",
                    "score": 0.85,
                    "metadata": {
                        "title": "Test Document 2",
                        "source": "Test Source 2",
                        "category": "test",
                        "content": "Test content 2",
                        "url": "",  # Empty URL
                        "published": "",
                    },
                },
            ]
        }

        mock_index.query.return_value = mock_query_results
        self.client.get_index = Mock(return_value=mock_index)

        # Call query_similar with embedding vector
        test_embedding = [0.1] * 768
        results = self.client.query_similar(test_embedding)

        # Verify results include URL metadata
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"

        # Check first result
        assert (
            results[0]["url"] == "https://example.com/doc1"
        ), "First result URL should match query metadata"
        assert (
            results[0]["published"] == "2024-01-01"
        ), "First result published date should match query metadata"

        # Check second result (empty URL)
        assert results[1]["url"] == "", "Second result should have empty URL as stored"
        assert (
            results[1]["published"] == ""
        ), "Second result should have empty published date as stored"

        # Verify all results have URL and published fields
        for i, result in enumerate(results):
            assert "url" in result, f"Result {i} missing 'url' field"
            assert "published" in result, f"Result {i} missing 'published' field"

    def test_upsert_documents_handles_invalid_urls_gracefully(self):
        """Test that invalid URLs are handled gracefully during upsert"""
        # Mock the index
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)

        # Test documents with invalid URLs
        documents = [
            {
                "id": "doc1",
                "title": "Test Document 1",
                "content": "This is test content 1",
                "source": "Test Source 1",
                "category": "test",
                "url": "invalid-url",
                "embedding": [0.1] * 768,
            },
            {
                "id": "doc2",
                "title": "Test Document 2",
                "content": "This is test content 2",
                "source": "Test Source 2",
                "category": "test",
                "url": None,
                "embedding": [0.2] * 768,
            },
        ]

        # This should not raise an exception
        try:
            self.client.upsert_documents(documents)
        except Exception as e:
            self.fail(f"upsert_documents raised an exception with invalid URLs: {e}")

        # Verify upsert was called
        mock_index.upsert.assert_called_once()

        # Get the vectors that were upserted
        call_args = mock_index.upsert.call_args[1]["vectors"]

        # Verify both documents have empty URL (invalid URLs become empty strings)
        assert (
            call_args[0]["metadata"]["url"] == ""
        ), "Invalid URL should result in empty string, not cause failure"
        assert (
            call_args[1]["metadata"]["url"] == ""
        ), "None URL should result in empty string, not cause failure"

    def test_invalid_paths_handling(self):
        """Test handling of invalid file paths and malformed data"""
        # Test with invalid document structures
        invalid_documents = [
            # Missing required fields
            {"id": "incomplete1"},
            # Invalid embedding type
            {"id": "invalid_embed", "title": "Test", "embedding": "not-a-list"},
            # Wrong embedding dimension
            {
                "id": "wrong_dim",
                "title": "Test",
                "embedding": [0.1] * 100,
            },  # Wrong dimension
            # Invalid metadata types
            {"id": "bad_metadata", "title": 123, "content": None, "url": 456},
        ]

        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)

        # Should handle invalid documents gracefully
        try:
            self.client.upsert_documents(invalid_documents)
        except Exception as e:
            # If it fails, the error should be informative
            assert (
                "dimension" in str(e).lower() or "embedding" in str(e).lower()
            ), f"Expected dimension/embedding error, got: {e}"

    def test_missing_config_keys(self):
        """Test behavior with missing configuration keys"""
        # Test missing API key
        with patch("src.utils.config.Config") as mock_config:
            mock_config.validate.return_value = None
            mock_config.PINECONE_API_KEY = None  # Missing API key
            mock_config.PINECONE_INDEX_NAME = "test-index"
            mock_config.EMBEDDING_DIMENSION = 768

            try:
                with patch("src.retrieval.pinecone_client.Pinecone"):
                    client = PineconeClient()
                    # Should handle missing API key appropriately
                    assert hasattr(
                        client, "validate_and_sanitize_url"
                    ), "Client should still be instantiable with missing API key"
            except Exception as e:
                assert (
                    "api" in str(e).lower() or "key" in str(e).lower()
                ), f"Expected API key error, got: {e}"

        # Test missing index name
        with patch("src.utils.config.Config") as mock_config:
            mock_config.validate.return_value = None
            mock_config.PINECONE_API_KEY = "test-key"
            mock_config.PINECONE_INDEX_NAME = None  # Missing index name
            mock_config.EMBEDDING_DIMENSION = 768

            try:
                with patch("src.retrieval.pinecone_client.Pinecone"):
                    client = PineconeClient()
                    assert hasattr(
                        client, "validate_and_sanitize_url"
                    ), "Client should handle missing index name"
            except Exception as e:
                assert "index" in str(e).lower(), f"Expected index name error, got: {e}"

    def test_boundary_values_embedding_dimensions(self):
        """Test boundary values for embedding dimensions"""
        boundary_test_cases = [
            # Minimum dimension
            {"dimension": 1, "embedding": [0.5]},
            # Very small dimension
            {"dimension": 2, "embedding": [0.1, 0.9]},
            # Large dimension (common in practice)
            {"dimension": 1536, "embedding": [0.1] * 1536},
            # Very large dimension
            {"dimension": 4096, "embedding": [0.1] * 4096},
        ]

        for test_case in boundary_test_cases:
            with patch("src.utils.config.Config") as mock_config:
                mock_config.validate.return_value = None
                mock_config.PINECONE_API_KEY = "test-key"
                mock_config.PINECONE_INDEX_NAME = "test-index"
                mock_config.EMBEDDING_DIMENSION = test_case["dimension"]

                with patch("src.retrieval.pinecone_client.Pinecone"):
                    client = PineconeClient()
                    mock_index = Mock()
                    client.get_index = Mock(return_value=mock_index)

                    document = {
                        "id": f'test_dim_{test_case["dimension"]}',
                        "title": "Test Document",
                        "content": "Test content",
                        "url": "https://example.com",
                        "embedding": test_case["embedding"],
                    }

                    # Should handle various embedding dimensions
                    client.upsert_documents([document])
                    mock_index.upsert.assert_called()

                    # Verify the embedding dimension matches
                    call_args = mock_index.upsert.call_args[1]["vectors"]
                    actual_embedding = call_args[0]["values"]
                    assert (
                        len(actual_embedding) == test_case["dimension"]
                    ), f"Embedding dimension should be {test_case['dimension']}, got {len(actual_embedding)}"

    def test_boundary_values_url_lengths(self):
        """Test boundary values for URL lengths"""
        # Test very short URLs
        short_url = "https://a.co"
        result = self.client.validate_and_sanitize_url(short_url)
        assert result == short_url, f"Short URL should be valid, got {result}"

        # Test maximum reasonable URL length (browsers typically limit to ~2048 chars)
        long_path = "a" * 2000
        long_url = f"https://example.com/{long_path}"
        result = self.client.validate_and_sanitize_url(long_url)
        # Should either accept or reject consistently
        assert (
            result == long_url or result is None
        ), f"Long URL should be handled consistently, got {result}"

        # Test extremely long URL (should be rejected)
        extremely_long_path = "a" * 10000
        extremely_long_url = f"https://example.com/{extremely_long_path}"
        result = self.client.validate_and_sanitize_url(extremely_long_url)
        # Most implementations should reject extremely long URLs
        assert (
            result is None or len(result) < 5000
        ), f"Extremely long URL should be rejected or truncated, got length {len(result) if result else 0}"

    def test_edge_case_query_parameters(self):
        """Test edge cases in query parameters for similar search"""
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)

        # Test with zero-dimension embedding (edge case)
        try:
            empty_embedding = []
            self.client.query_similar(empty_embedding)
        except Exception as e:
            assert (
                "embedding" in str(e).lower() or "dimension" in str(e).lower()
            ), f"Expected embedding dimension error for empty embedding, got: {e}"

        # Test with negative values in embedding
        negative_embedding = [-0.5] * 768
        mock_index.query.return_value = {"matches": []}
        results = self.client.query_similar(negative_embedding)
        assert isinstance(
            results, list
        ), "Query with negative embedding values should return list"

        # Test with extreme values in embedding
        extreme_embedding = [float("inf")] * 768
        try:
            self.client.query_similar(extreme_embedding)
        except Exception as e:
            assert (
                "float" in str(e).lower() or "inf" in str(e).lower()
            ), f"Expected float/infinity error for extreme values, got: {e}"

    def test_malformed_metadata_edge_cases(self):
        """Test handling of malformed metadata structures"""
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)

        # Test documents with malformed metadata
        malformed_documents = [
            {
                "id": "nested_dict",
                "title": "Test",
                "content": "Content",
                "metadata": {"nested": {"deep": "value"}},  # Nested metadata
                "embedding": [0.1] * 768,
            },
            {
                "id": "circular_ref",
                "title": "Test",
                "content": "Content",
                "embedding": [0.1] * 768,
                # Note: Can't easily create circular reference in test
            },
        ]

        # Should handle malformed metadata gracefully
        try:
            self.client.upsert_documents(malformed_documents)
            mock_index.upsert.assert_called()
        except Exception as e:
            # If it fails, should be due to metadata structure
            assert (
                "metadata" in str(e).lower() or "structure" in str(e).lower()
            ), f"Expected metadata structure error, got: {e}"


def main():
    """Run the tests"""
    print("🧪 Testing Pinecone URL Metadata Functionality")
    print("=" * 50)

    # Run the unit tests
    unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
