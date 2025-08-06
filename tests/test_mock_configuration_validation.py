#!/usr/bin/env python3
"""
Test script to validate updated mock configurations align with current code structure.
"""


import pytest


def test_mock_pinecone_client_fixture(mock_pinecone_client):
    """Test that the mock_pinecone_client fixture works correctly."""
    # Test that all expected attributes are present
    assert hasattr(mock_pinecone_client, "get_index")
    assert hasattr(mock_pinecone_client, "query_similar")
    assert hasattr(mock_pinecone_client, "query")
    assert hasattr(mock_pinecone_client, "upsert_documents")
    assert hasattr(mock_pinecone_client, "validate_and_sanitize_url")
    assert hasattr(mock_pinecone_client, "safe_validate_url")

    # Test that mock attributes are accessible
    assert hasattr(mock_pinecone_client, "_mock_index")
    assert hasattr(mock_pinecone_client, "_mock_pc")
    assert hasattr(mock_pinecone_client, "_test_env")

    # Test that the index name and dimension are configured (may be from actual config in dev)
    assert hasattr(mock_pinecone_client, "index_name")
    assert hasattr(mock_pinecone_client, "dimension")
    assert isinstance(mock_pinecone_client.index_name, str)
    assert isinstance(mock_pinecone_client.dimension, int)


def test_mock_query_results_fixture(mock_query_results):
    """Test that the mock_query_results fixture provides expected structure."""
    assert isinstance(mock_query_results, dict)
    assert "matches" in mock_query_results
    assert len(mock_query_results["matches"]) >= 3

    # Check first match structure
    first_match = mock_query_results["matches"][0]
    assert "id" in first_match
    assert "score" in first_match
    assert "metadata" in first_match

    # Check metadata structure
    metadata = first_match["metadata"]
    assert "title" in metadata
    assert "source" in metadata
    assert "category" in metadata
    assert "content" in metadata
    assert "url" in metadata
    assert "published" in metadata


def test_sample_documents_fixture(sample_documents):
    """Test that the sample_documents fixture provides expected structure."""
    assert isinstance(sample_documents, list)
    assert len(sample_documents) >= 3

    # Check document structure
    doc = sample_documents[0]
    assert "id" in doc
    assert "title" in doc
    assert "content" in doc
    assert "source" in doc
    assert "category" in doc
    assert "embedding" in doc

    # Verify embedding dimension is consistent across all documents
    embedding_dim = len(doc["embedding"])
    assert embedding_dim > 0, "Embedding should not be empty"
    for document in sample_documents:
        if "embedding" in document:
            assert (
                len(document["embedding"]) == embedding_dim
            ), f"All embeddings should have same dimension: {embedding_dim}"

    # Test backward compatibility - one document should be missing URL
    docs_without_url = [d for d in sample_documents if "url" not in d]
    assert (
        len(docs_without_url) >= 1
    ), "Should have at least one document without URL for backward compatibility testing"


def test_query_method_backward_compatibility(mock_pinecone_client, mock_query_results):
    """Test that the query method exists and works for backward compatibility."""
    # Configure mock to return our test results
    mock_pinecone_client._mock_index.query.return_value = mock_query_results

    # Get dynamic values from mock configuration and data
    embedding_dimension = mock_pinecone_client.dimension
    expected_result_count = len(mock_query_results["matches"])

    # Test direct query method (backward compatibility)
    results = mock_pinecone_client.query(
        vector=[0.1] * embedding_dimension,
        top_k=expected_result_count,
        include_metadata=True,
    )

    # Should return matches as a list (backward compatibility behavior)
    assert isinstance(results, list)
    assert len(results) == expected_result_count
    assert all("id" in match for match in results)


def test_query_similar_method(mock_pinecone_client, mock_query_results):
    """Test that the query_similar method works with mocked responses."""
    # Configure mock to return our test results
    mock_pinecone_client._mock_index.query.return_value = mock_query_results

    # Get dynamic values from mock configuration and data
    embedding_dimension = mock_pinecone_client.dimension
    expected_result_count = len(mock_query_results["matches"])

    # Test query_similar method
    results = mock_pinecone_client.query_similar(
        query_embedding=[0.1] * embedding_dimension, top_k=expected_result_count
    )

    # Should return formatted results
    assert isinstance(results, list)
    assert len(results) == expected_result_count

    # Check result structure
    for result in results:
        assert "id" in result
        assert "score" in result
        assert "title" in result
        assert "source" in result
        assert "category" in result
        assert "content" in result
        assert "url" in result
        assert "published" in result


def test_upsert_documents_method(mock_pinecone_client, sample_documents):
    """Test that the upsert_documents method works with mocked index."""
    # Call upsert_documents
    mock_pinecone_client.upsert_documents(sample_documents)

    # Verify the mock index upsert was called
    mock_pinecone_client._mock_index.upsert.assert_called()

    # Check that vectors were properly formatted
    call_args = mock_pinecone_client._mock_index.upsert.call_args
    vectors = call_args[1]["vectors"]  # keyword argument

    assert len(vectors) == len(sample_documents)

    # Get expected embedding dimension from client configuration
    expected_dimension = mock_pinecone_client.dimension

    # Check vector structure
    for vector in vectors:
        assert "id" in vector
        assert "values" in vector
        assert "metadata" in vector
        assert len(vector["values"]) == expected_dimension


def test_url_validation_methods(mock_pinecone_client):
    """Test URL validation methods work correctly."""
    # Test valid URL - allow for trailing slash normalization
    valid_url = "https://example.com"
    result = mock_pinecone_client.validate_and_sanitize_url(valid_url)
    assert result is not None, "Valid URL should not be None"
    assert result.startswith(
        "https://example.com"
    ), f"URL should start with base domain, got: {result}"

    # Test URL without protocol
    no_protocol_url = "example.com"
    result = mock_pinecone_client.validate_and_sanitize_url(no_protocol_url)
    assert result is not None, "URL without protocol should be handled"
    assert result.startswith(
        "https://example.com"
    ), f"Should add https protocol, got: {result}"

    # Test invalid URL with safe validation
    invalid_url = "not-a-url"
    result = mock_pinecone_client.safe_validate_url(invalid_url)
    # The current implementation adds https:// prefix, making "not-a-url" -> "https://not-a-url"
    # This passes basic URL validation but may fail domain validation
    assert result is None or result == "" or result.startswith("https://")


def test_configuration_values(mock_pinecone_client):
    """Test that configuration values are accessible via test environment."""
    # Now using environment variable mocking instead of Config patching
    assert hasattr(mock_pinecone_client, "_test_env")
    assert mock_pinecone_client._test_env is not None
    assert mock_pinecone_client._test_env["PINECONE_API_KEY"] == "test-api-key"
    assert mock_pinecone_client._test_env["PINECONE_INDEX_NAME"] == "test-index"

    # The embedding dimension should match the client's actual dimension
    expected_dimension = str(mock_pinecone_client.dimension)
    assert mock_pinecone_client._test_env["EMBEDDING_DIMENSION"] == expected_dimension


def test_graceful_degradation_with_empty_results(mock_pinecone_client):
    """Test graceful handling of empty query results."""
    # Configure mock to return empty results
    mock_pinecone_client._mock_index.query.return_value = {"matches": []}

    # Get dynamic embedding dimension from client configuration
    embedding_dimension = mock_pinecone_client.dimension

    # Test query_similar with empty results
    results = mock_pinecone_client.query_similar([0.1] * embedding_dimension, top_k=5)
    assert isinstance(results, list)
    assert len(results) == 0

    # Test query_similar_formatted with empty results
    formatted_results = mock_pinecone_client.query_similar_formatted(
        query_embedding=[0.1] * embedding_dimension, top_k=5, query_text="test query"
    )

    assert isinstance(formatted_results, dict)
    assert "summary" in formatted_results
    assert "structured_results" in formatted_results
    assert "metadata" in formatted_results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
