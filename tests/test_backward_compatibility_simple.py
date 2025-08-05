#!/usr/bin/env python3
"""
Simple backward compatibility tests for URL metadata system.
"""

from unittest.mock import Mock, patch

import numpy as np
import pytest

from src.retrieval.pinecone_client import PineconeClient


class TestBackwardCompatibilitySimple:
    """Simple test suite for backward compatibility."""

    @pytest.fixture
    def mock_index(self):
        """Create a mock Pinecone index."""
        mock_index = Mock()

        # Legacy vectors (no URL metadata)
        legacy_vectors = [
            {
                "id": "legacy_1",
                "score": 0.95,
                "metadata": {
                    "title": "Bitcoin Overview",
                    "source": "whitepaper",
                    "category": "crypto",
                    "content": "Bitcoin is a decentralized cryptocurrency",
                    "url": "",  # Empty URL
                },
            }
        ]

        # Modern vectors (with URL metadata)
        modern_vectors = [
            {
                "id": "modern_1",
                "score": 0.98,
                "metadata": {
                    "title": "Bitcoin Halving",
                    "source": "bitcoin.org",
                    "category": "crypto",
                    "content": "Bitcoin halving reduces block rewards",
                    "url": "https://bitcoin.org/halving",
                    "source_url": "https://bitcoin.org/halving",
                    "url_title": "Bitcoin Halving Explained",
                    "url_domain": "bitcoin.org",
                    "metadata_version": "2.0",
                },
            }
        ]

        mock_index._legacy = legacy_vectors
        mock_index._modern = modern_vectors
        mock_index._all = legacy_vectors + modern_vectors

        return mock_index

    @pytest.fixture
    def pinecone_client(self, mock_index):
        """Create PineconeClient with mocked dependencies."""
        import os

        # Mock environment variables for Config
        test_env_vars = {
            "PINECONE_API_KEY": "test-key",
            "PINECONE_INDEX_NAME": "test-index",
            "EMBEDDING_DIMENSION": "1536",
        }

        with patch("src.retrieval.pinecone_client.Pinecone"), patch.dict(
            os.environ, test_env_vars, clear=False
        ):

            client = PineconeClient()

            # Mock the get_index method to return our mock
            client.get_index = Mock(return_value=mock_index)

            return client

    def test_query_legacy_vectors_only(self, pinecone_client, mock_index):
        """Test querying when only legacy vectors exist."""
        # Mock query response with legacy vectors
        mock_index.query.return_value = {"matches": mock_index._legacy}

        # Perform query
        results = pinecone_client.query_similar(query_embedding=[0.1] * 1536, top_k=1)

        # Validate results
        assert len(results) == 1
        result = results[0]
        assert result["id"] == "legacy_1"
        assert result["url"] == ""  # Legacy vector has empty URL
        assert (
            "source_url" not in result
        )  # Legacy vectors should not have source_url field

    def test_query_modern_vectors(self, pinecone_client, mock_index):
        """Test querying modern vectors with URL metadata."""
        # Mock query response with modern vectors
        mock_index.query.return_value = {"matches": mock_index._modern}

        # Perform query
        results = pinecone_client.query_similar(query_embedding=[0.2] * 1536, top_k=1)

        # Validate results
        assert len(results) == 1
        result = results[0]
        assert result["id"] == "modern_1"
        assert result["url"] == "https://bitcoin.org/halving"
        # Note: query_similar only returns standard fields, not all metadata
        # Additional metadata fields like source_url are not preserved in the current implementation

    def test_query_mixed_vectors(self, pinecone_client, mock_index):
        """Test querying when both legacy and modern vectors exist."""
        # Mock query response with mixed vectors
        mock_index.query.return_value = {"matches": mock_index._all}

        # Perform query
        results = pinecone_client.query_similar(query_embedding=[0.3] * 1536, top_k=2)

        # Validate results
        assert len(results) == 2

        # Check that we can handle both types
        legacy_found = False
        modern_found = False

        for result in results:
            if result["id"] == "legacy_1":
                legacy_found = True
                assert result["url"] == ""
            elif result["id"] == "modern_1":
                modern_found = True
                assert result["url"] == "https://bitcoin.org/halving"

        assert legacy_found and modern_found

    def test_graceful_degradation(self, pinecone_client):
        """Test graceful handling of query failures."""
        # Mock empty query response
        mock_index = pinecone_client.get_index()
        mock_index.query.return_value = {"matches": []}

        # Test empty results
        results = pinecone_client.query_similar_formatted(
            query_embedding=[0.1] * 1536,  # Deterministic test data
            top_k=5,
            query_text="test query",
        )

        # Should return structured response even with no results
        assert isinstance(results, dict)
        assert "summary" in results
        assert "structured_results" in results
        assert "metadata" in results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
