#!/usr/bin/env python3
"""
Pytest fixtures for URL metadata logging tests.

This module provides reusable fixtures for testing URL metadata functionality,
including temporary directory management and pre-built configuration objects.

It also centralizes project import path setup (autouse session fixture)
so tests do not need to mutate sys.path inline, resolving Ruff E402 warnings.
"""

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Session-scoped fixture that automatically sets up the test environment.

    Ensures repository imports work without per-file sys.path hacks by placing
    repository root and src/ on sys.path for the duration of the test session.
    """
    import sys
    from pathlib import Path

    tests_dir = Path(__file__).resolve().parent
    repo_root = tests_dir.parent
    src_dir = repo_root / "src"

    original_path = sys.path.copy()

    # Prepend repo root and src so both "src.*" and project-local imports work.
    repo_root_str = str(repo_root)
    src_str = str(src_dir)

    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

    try:
        yield
    finally:
        # Restore original sys.path
        sys.path[:] = original_path


@dataclass
class QueryTruncationConfig:
    """Configuration object for query truncation settings."""

    query_truncation_length: int = 100
    log_dir: str = "logs"

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
        return {
            "query_truncation_length": self.query_truncation_length,
            "log_dir": self.log_dir,
        }


@pytest.fixture
def temp_config_dir(tmp_path):
    """
    Provides a temporary directory with mock config files.

    Creates a temporary directory structure with common config files
    that tests can use for URL metadata logging operations.

    Args:
        tmp_path: pytest's built-in temporary directory fixture

    Returns:
        Path: Path to the temporary directory containing config files

    Example:
        def test_config_loading(temp_config_dir):
            config_file = temp_config_dir / "config.json"
            assert config_file.exists()
    """
    # Create subdirectories for different types of configs
    config_dir = tmp_path / "config"
    logs_dir = tmp_path / "logs"
    test_data_dir = tmp_path / "test_data"

    config_dir.mkdir()
    logs_dir.mkdir()
    test_data_dir.mkdir()

    # Create a basic config file
    basic_config = {
        "query_truncation_length": 100,
        "log_rotation_max_bytes": 50 * 1024 * 1024,
        "log_rotation_backup_count": 5,
        "alert_thresholds": {
            "validation_failure_rate": 0.10,
            "upload_failure_rate": 0.05,
            "retry_max_attempts": 5,
            "response_time_ms": 5000,
        },
    }

    import json

    with open(config_dir / "basic_config.json", "w") as f:
        json.dump(basic_config, f, indent=2)

    # Create a custom config with different truncation length
    custom_config = basic_config.copy()
    custom_config["query_truncation_length"] = 200

    with open(config_dir / "custom_config.json", "w") as f:
        json.dump(custom_config, f, indent=2)

    # Create a minimal config
    minimal_config = {"query_truncation_length": 50}

    with open(config_dir / "minimal_config.json", "w") as f:
        json.dump(minimal_config, f, indent=2)

    # Create some test log files for testing existing log handling
    sample_log_entries = [
        '{"timestamp": "2024-01-01T12:00:00Z", "level": "INFO", "message": "Test log entry 1"}',
        '{"timestamp": "2024-01-01T12:01:00Z", "level": "WARNING", "message": "Test log entry 2"}',
        '{"timestamp": "2024-01-01T12:02:00Z", "level": "ERROR", "message": "Test log entry 3"}',
    ]

    with open(logs_dir / "sample.log", "w") as f:
        for entry in sample_log_entries:
            f.write(entry + "\n")

    return tmp_path


@pytest.fixture
def default_query_config():
    """
    Provides a default QueryTruncationConfig object.

    Returns:
        QueryTruncationConfig: Configuration with default settings (100 char truncation)

    Example:
        def test_default_config(default_query_config):
            assert default_query_config.query_truncation_length == 100
    """
    return QueryTruncationConfig(query_truncation_length=100, log_dir="logs")


@pytest.fixture
def custom_query_config():
    """
    Provides a QueryTruncationConfig object with custom settings.

    Returns:
        QueryTruncationConfig: Configuration with 200 character truncation

    Example:
        def test_custom_config(custom_query_config):
            assert custom_query_config.query_truncation_length == 200
    """
    return QueryTruncationConfig(query_truncation_length=200, log_dir="custom_logs")


@pytest.fixture
def short_query_config():
    """
    Provides a QueryTruncationConfig object with short truncation length.

    Returns:
        QueryTruncationConfig: Configuration with 50 character truncation

    Example:
        def test_short_config(short_query_config):
            assert short_query_config.query_truncation_length == 50
    """
    return QueryTruncationConfig(query_truncation_length=50, log_dir="short_logs")


@pytest.fixture
def config_variants():
    """
    Provides multiple QueryTruncationConfig variants for parameterized tests.

    Returns:
        Dict[str, QueryTruncationConfig]: Dictionary of named configuration variants

    Example:
        def test_all_configs(config_variants):
            for name, config in config_variants.items():
                print(f"Testing {name}: {config.query_truncation_length}")
    """
    return {
        "default": QueryTruncationConfig(
            query_truncation_length=100, log_dir="default_logs"
        ),
        "custom": QueryTruncationConfig(
            query_truncation_length=200, log_dir="custom_logs"
        ),
        "short": QueryTruncationConfig(
            query_truncation_length=50, log_dir="short_logs"
        ),
        "extended": QueryTruncationConfig(
            query_truncation_length=500, log_dir="extended_logs"
        ),
        "minimal": QueryTruncationConfig(
            query_truncation_length=25, log_dir="minimal_logs"
        ),
    }


@pytest.fixture
def mock_url_metadata_logger():
    """
    Provides a mock URLMetadataLogger instance for testing.

    Creates a logger instance with a temporary directory that gets
    cleaned up automatically after the test.

    Returns:
        URLMetadataLogger: Logger instance configured with temporary directory

    Example:
        def test_logger_operations(mock_url_metadata_logger):
            mock_url_metadata_logger.log_retrieval("test query", 5, 100.0)
    """
    try:
        from src.utils.url_metadata_logger import URLMetadataLogger
    except ImportError:
        pytest.skip("URLMetadataLogger not available")

    # Create a temporary directory for this logger instance
    temp_dir = tempfile.mkdtemp()

    try:
        logger = URLMetadataLogger(log_dir=temp_dir, query_truncation_length=100)
        yield logger
    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_pinecone_client():
    """
    Provides a properly mocked PineconeClient for testing.

    This fixture handles all the necessary patching and configuration
    to create a working PineconeClient instance for tests.

    Returns:
        PineconeClient: Fully mocked client instance
    """
    import os
    from unittest.mock import Mock, patch

    try:
        from src.retrieval.pinecone_client import PineconeClient
    except ImportError:
        pytest.skip("PineconeClient not available")

    # Get the dynamic embedding dimension from the current environment or use default

    embedding_dimension = os.getenv("EMBEDDING_DIMENSION", "768")

    # Mock environment variables for Config instead of patching Config class
    test_env_vars = {
        "PINECONE_API_KEY": "test-api-key",
        "PINECONE_INDEX_NAME": "test-index",
        "EMBEDDING_DIMENSION": embedding_dimension,
    }

    # Mock external dependencies
    with (
        patch("src.retrieval.pinecone_client.Pinecone") as mock_pinecone,
        patch.dict(os.environ, test_env_vars, clear=False),
    ):
        # Configure the Pinecone mock
        mock_pc_instance = Mock()
        mock_pinecone.return_value = mock_pc_instance

        # Create mock index
        mock_index = Mock()
        mock_pc_instance.Index.return_value = mock_index
        mock_pc_instance.list_indexes.return_value.names.return_value = []

        # Initialize the client
        client = PineconeClient()

        # Override the get_index method to return our mock instead of calling Pinecone API
        def mock_get_index():
            return mock_index

        client.get_index = mock_get_index

        # Attach mocks for easy access in tests
        client._mock_index = mock_index
        client._mock_pc = mock_pc_instance
        client._test_env = test_env_vars

        yield client


@pytest.fixture
def mock_query_results():
    """
    Provides sample query results for testing.

    Returns:
        Dict: Mock query results with matches
    """
    return {
        "matches": [
            {
                "id": "doc1",
                "score": 0.95,
                "metadata": {
                    "title": "Bitcoin Whitepaper",
                    "source": "bitcoin.org",
                    "category": "documentation",
                    "content": "Bitcoin: A Peer-to-Peer Electronic Cash System",
                    "url": "https://bitcoin.org/bitcoin.pdf",
                    "published": "2008-10-31",
                },
            },
            {
                "id": "doc2",
                "score": 0.87,
                "metadata": {
                    "title": "Bitcoin Mining Guide",
                    "source": "developer.bitcoin.org",
                    "category": "tutorial",
                    "content": "Understanding Bitcoin mining and proof of work",
                    "url": "https://developer.bitcoin.org/devguide/mining.html",
                    "published": "2021-03-15",
                },
            },
            {
                "id": "doc3",
                "score": 0.82,
                "metadata": {
                    "title": "Legacy Document",
                    "source": "internal",
                    "category": "legacy",
                    "content": "Document without URL metadata",
                    "url": "",  # Empty URL for backward compatibility testing
                    "published": "",
                },
            },
        ]
    }


@pytest.fixture
def sample_documents():
    """
    Provides sample documents for upsert testing.

    Returns:
        List[Dict]: Sample documents with embeddings
    """
    # Get the dynamic embedding dimension from the config
    import os

    embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    return [
        {
            "id": "test_doc_1",
            "title": "Test Document 1",
            "content": "This is a test document with a valid URL",
            "source": "test_source",
            "category": "test",
            "url": "https://example.com/doc1",
            "published": "2024-01-01",
            "embedding": [0.1] * embedding_dimension,
        },
        {
            "id": "test_doc_2",
            "title": "Test Document 2",
            "content": "This is a test document without a URL",
            "source": "test_source_2",
            "category": "test",
            "embedding": [0.2] * embedding_dimension,
            # No URL field to test backward compatibility
        },
        {
            "id": "test_doc_3",
            "title": "Test Document 3",
            "content": "This is a test document with an invalid URL",
            "source": "test_source_3",
            "category": "test",
            "url": "invalid-url-format",
            "embedding": [0.3] * embedding_dimension,
        },
    ]


@pytest.fixture
def parameterized_logger_configs():
    """
    Provides parameterized logger configurations for comprehensive testing.

    Returns:
        List[Dict[str, Any]]: List of logger configuration dictionaries

    Example:
        @pytest.mark.parametrize("config", parameterized_logger_configs())
        def test_logger_with_config(config):
            logger = URLMetadataLogger(**config)
    """
    return [
        {"query_truncation_length": 50, "log_dir": "test_logs_50"},
        {"query_truncation_length": 100, "log_dir": "test_logs_100"},
        {"query_truncation_length": 200, "log_dir": "test_logs_200"},
        {"query_truncation_length": 500, "log_dir": "test_logs_500"},
    ]


@pytest.fixture
def sample_test_data():
    """
    Provides sample test data for URL metadata operations.

    Returns:
        Dict[str, Any]: Dictionary containing sample URLs, queries, and metadata

    Example:
        def test_with_sample_data(sample_test_data):
            for url in sample_test_data['urls']:
                # Test URL processing
                pass
    """
    return {
        "urls": [
            "https://bitcoin.org",
            "https://github.com/bitcoin/bitcoin",
            "https://bitcointalk.org",
            "https://en.bitcoin.it/wiki/Bitcoin",
            "https://developer.bitcoin.org",
        ],
        "queries": [
            "What is Bitcoin?",
            "How does Bitcoin mining work?",
            "Bitcoin transaction fees explained",
            "A" * 150,  # Long query for truncation testing
            "Bitcoin halving mechanism and economic impact on cryptocurrency market dynamics",
        ],
        "metadata": {
            "categories": ["crypto", "blockchain", "finance", "technology"],
            "sources": ["whitepaper", "documentation", "forum", "wiki", "official"],
            "confidence_scores": [0.95, 0.87, 0.92, 0.78, 0.89],
        },
        "expected_truncations": {
            50: {
                "A" * 150: "A" * 50,
                "Bitcoin halving mechanism and economic impact on cryptocurrency market dynamics": (
                    (
                        "Bitcoin halving mechanism and economic impact on cryptocurrency "
                    )[:50]
                ),
            },
            100: {
                "A" * 150: "A" * 100,
                "Bitcoin halving mechanism and economic impact on cryptocurrency market dynamics": (
                    "Bitcoin halving mechanism and economic impact on cryptocurrency market dynamics"
                )[:100],
            },
            200: {
                "A" * 150: "A" * 150,  # Shorter than limit
                "Bitcoin halving mechanism and economic impact on cryptocurrency market dynamics": (
                    "Bitcoin halving mechanism and economic impact on cryptocurrency market dynamics"
                ),
            },
        },
    }


@pytest.fixture(scope="session")
def session_temp_dir():
    """
    Provides a session-scoped temporary directory for expensive setup operations.

    This directory persists across all tests in the session and is cleaned up
    at the end of the test session.

    Returns:
        Path: Path to the session-scoped temporary directory

    Example:
        def test_session_setup(session_temp_dir):
            # Use for expensive operations that can be shared across tests
            pass
    """
    temp_dir = tempfile.mkdtemp(prefix="pytest_session_")
    temp_path = Path(temp_dir)

    yield temp_path

    # Clean up at end of session
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_pinecone_index():
    """
    Provides a mock Pinecone index with comprehensive test data.

    Returns:
        Mock: Configured mock index with legacy and modern vectors
    """
    from unittest.mock import Mock

    mock_index = Mock()

    # Legacy vectors (no URL metadata)
    legacy_vectors = [
        {
            "id": "legacy_1",
            "values": [0.1] * 1536,
            "metadata": {
                "text": "Bitcoin is a decentralized cryptocurrency",
                "timestamp": "2023-01-01T00:00:00Z",
                "title": "Bitcoin Overview",
                "source": "whitepaper",
                "category": "crypto",
                "content": "Bitcoin is a decentralized cryptocurrency",
                "url": "",
                "published": "",
            },
            "score": 0.95,
        },
        {
            "id": "legacy_2",
            "values": [0.2] * 1536,
            "metadata": {
                "text": "Blockchain enables trustless transactions",
                "timestamp": "2023-01-02T00:00:00Z",
                "title": "Blockchain Technology",
                "source": "research",
                "category": "technology",
                "content": "Blockchain enables trustless transactions",
                "url": "",
                "published": "",
            },
            "score": 0.92,
        },
    ]

    # Modern vectors (with URL metadata)
    modern_vectors = [
        {
            "id": "modern_1",
            "values": [0.3] * 1536,
            "metadata": {
                "text": "Bitcoin halving reduces block rewards",
                "timestamp": "2024-01-01T00:00:00Z",
                "title": "Bitcoin Halving",
                "source": "bitcoin.org",
                "category": "crypto",
                "content": "Bitcoin halving reduces block rewards",
                "url": "https://bitcoin.org/halving",
                "published": "2024-01-01",
                "source_url": "https://bitcoin.org/halving",
                "url_title": "Bitcoin Halving Explained",
                "url_domain": "bitcoin.org",
                "metadata_version": "2.0",
            },
            "score": 0.98,
        },
        {
            "id": "modern_2",
            "values": [0.4] * 1536,
            "metadata": {
                "text": "Lightning Network enables fast transactions",
                "timestamp": "2024-01-02T00:00:00Z",
                "title": "Lightning Network",
                "source": "lightning.network",
                "category": "technology",
                "content": "Lightning Network enables fast transactions",
                "url": "https://lightning.network/docs",
                "published": "2024-01-02",
                "source_url": "https://lightning.network/docs",
                "url_title": "Lightning Documentation",
                "url_domain": "lightning.network",
                "metadata_version": "2.0",
            },
            "score": 0.94,
        },
    ]

    # Store different vector sets for testing
    mock_index._legacy_vectors = legacy_vectors
    mock_index._modern_vectors = modern_vectors
    mock_index._all_vectors = legacy_vectors + modern_vectors

    # Configure default return behavior
    mock_index.query.return_value = {"matches": mock_index._all_vectors}
    mock_index.upsert.return_value = None
    mock_index.delete.return_value = None
    mock_index.update.return_value = None
    mock_index.describe_index_stats.return_value = {
        "dimension": 1536,
        "index_fullness": 0.1,
        "namespaces": {},
        "total_vector_count": 4,
    }

    return mock_index


@pytest.fixture
def mock_assistant_agent():
    """
    Provides a mock PineconeAssistantAgent for testing.

    Returns:
        Mock: Configured mock assistant agent
    """
    from unittest.mock import Mock

    # Mock the assistant agent class
    mock_agent = Mock()

    # Configure common return values
    mock_agent.query_assistant.return_value = {
        "answer": "Test response from assistant",
        "sources": [
            {
                "title": "Test Source",
                "url": "https://example.com",
                "score": 0.95,
            }
        ],
        "metadata": {
            "query_time": 0.5,
            "total_results": 1,
        },
    }

    mock_agent.upload_documents.return_value = {
        "success": True,
        "uploaded_count": 5,
        "failed_count": 0,
    }

    mock_agent.create_assistant.return_value = {
        "id": "test-assistant-id",
        "name": "Test Assistant",
    }

    return mock_agent


@pytest.fixture
def mock_performance_metrics():
    """
    Provides mock performance metrics for testing.

    Returns:
        Dict: Mock performance metrics data
    """
    return {
        "query_latency": {
            "min": 0.1,
            "max": 2.5,
            "avg": 0.8,
            "p95": 1.5,
            "p99": 2.0,
        },
        "memory_usage": {
            "baseline": 512,  # MB
            "peak": 768,
            "average": 640,
        },
        "throughput": {
            "queries_per_second": 150,
            "concurrent_requests": 10,
        },
        "error_rates": {
            "total_requests": 1000,
            "failed_requests": 5,
            "error_rate": 0.005,
        },
    }


@pytest.fixture
def mock_migration_client():
    """
    Provides a mock migration client for testing data migrations.

    Returns:
        Mock: Configured mock migration client
    """
    from unittest.mock import Mock

    mock_client = Mock()

    # Mock migration operations
    mock_client.migrate_vectors.return_value = {
        "success": True,
        "migrated_count": 100,
        "failed_count": 0,
        "duration": 5.2,
    }

    mock_client.rollback_migration.return_value = {
        "success": True,
        "rolled_back_count": 50,
        "duration": 2.1,
    }

    mock_client.get_migration_status.return_value = {
        "status": "completed",
        "progress": 100,
        "total_vectors": 1000,
        "migrated_vectors": 1000,
    }

    return mock_client


@pytest.fixture
def legacy_vectors():
    """
    Provides sample legacy vectors without URL metadata.

    Returns:
        List[Dict]: Legacy vector data
    """
    return [
        {
            "id": "legacy_vec_1",
            "values": [0.1] * 1536,
            "metadata": {
                "text": "Legacy content without URLs",
                "timestamp": "2023-01-01T00:00:00Z",
                "category": "legacy",
            },
        },
        {
            "id": "legacy_vec_2",
            "values": [0.2] * 1536,
            "metadata": {
                "text": "Another legacy document",
                "timestamp": "2023-01-02T00:00:00Z",
                "category": "legacy",
            },
        },
    ]


@pytest.fixture
def modern_vectors():
    """
    Provides sample modern vectors with full URL metadata.

    Returns:
        List[Dict]: Modern vector data
    """
    return [
        {
            "id": "modern_vec_1",
            "values": [0.3] * 1536,
            "metadata": {
                "text": "Modern content with full URL metadata",
                "timestamp": "2024-01-01T00:00:00Z",
                "category": "modern",
                "source_url": "https://example.com/article1",
                "url_title": "Example Article 1",
                "url_domain": "example.com",
                "url_validated": True,
                "metadata_version": "2.0",
            },
        },
        {
            "id": "modern_vec_2",
            "values": [0.4] * 1536,
            "metadata": {
                "text": "Another modern document",
                "timestamp": "2024-01-02T00:00:00Z",
                "category": "modern",
                "source_url": "https://example.com/article2",
                "url_title": "Example Article 2",
                "url_domain": "example.com",
                "url_validated": True,
                "metadata_version": "2.0",
            },
        },
    ]


@pytest.fixture
def mixed_vectors(legacy_vectors, modern_vectors):
    """
    Provides a mix of legacy and modern vectors.

    Returns:
        List[Dict]: Combined legacy and modern vector data
    """
    return legacy_vectors + modern_vectors


@pytest.fixture
def mock_embedding_service():
    """
    Provides a mock embedding service for testing.

    Returns:
        Mock: Configured mock embedding service
    """
    from unittest.mock import Mock

    mock_service = Mock()

    # Mock embedding generation
    mock_service.generate_embedding.return_value = [0.1] * 1536
    mock_service.generate_embeddings.return_value = [[0.1] * 1536, [0.2] * 1536]

    # Mock service info
    mock_service.model_name = "text-embedding-ada-002"
    mock_service.dimension = 1536
    mock_service.max_tokens = 8191

    return mock_service


@pytest.fixture
def mock_url_validator():
    """
    Provides a mock URL validator for testing.

    Returns:
        Mock: Configured mock URL validator
    """
    from unittest.mock import Mock

    mock_validator = Mock()

    # Mock validation methods
    mock_validator.validate_url.return_value = True
    mock_validator.validate_urls.return_value = {
        "valid": ["https://example.com", "https://test.org"],
        "invalid": ["not-a-url", "http://"],
    }

    mock_validator.sanitize_url.side_effect = lambda url: (
        f"https://{url}" if not url.startswith(("http://", "https://")) else url
    )

    return mock_validator


@pytest.fixture
def mock_cache():
    """
    Provides a mock cache implementation for testing.

    Returns:
        Mock: Configured mock cache
    """
    from unittest.mock import Mock

    mock_cache = Mock()

    # Mock cache operations
    mock_cache.get.return_value = None  # Default cache miss
    mock_cache.set.return_value = True
    mock_cache.delete.return_value = True
    mock_cache.clear.return_value = True

    # Mock cache stats
    mock_cache.get_stats.return_value = {
        "hits": 150,
        "misses": 50,
        "hit_rate": 0.75,
        "size": 200,
    }

    return mock_cache


@pytest.fixture
def error_scenarios():
    """
    Provides common error scenarios for testing.

    Returns:
        Dict: Error scenarios with expected behaviors
    """
    return {
        "network_timeout": {
            "exception": TimeoutError("Network timeout"),
            "retry_count": 3,
            "expected_fallback": "cached_result",
        },
        "invalid_api_key": {
            "exception": ValueError("Invalid API key"),
            "retry_count": 0,
            "expected_fallback": "error_response",
        },
        "index_not_found": {
            "exception": FileNotFoundError("Index not found"),
            "retry_count": 1,
            "expected_fallback": "create_index",
        },
        "rate_limit": {
            "exception": RuntimeError("Rate limit exceeded"),
            "retry_count": 5,
            "expected_fallback": "exponential_backoff",
        },
    }


@pytest.fixture
def mock_logger():
    """
    Provides a mock logger for testing logging functionality.

    Returns:
        Mock: Configured mock logger
    """
    from unittest.mock import Mock

    mock_logger = Mock()

    # Mock all logging levels
    mock_logger.debug.return_value = None
    mock_logger.info.return_value = None
    mock_logger.warning.return_value = None
    mock_logger.error.return_value = None
    mock_logger.critical.return_value = None

    # Track call counts
    mock_logger.call_count = {
        "debug": 0,
        "info": 0,
        "warning": 0,
        "error": 0,
        "critical": 0,
    }

    def track_calls(level):
        def wrapper(*args, **kwargs):
            mock_logger.call_count[level] += 1

        return wrapper

    mock_logger.debug.side_effect = track_calls("debug")
    mock_logger.info.side_effect = track_calls("info")
    mock_logger.warning.side_effect = track_calls("warning")
    mock_logger.error.side_effect = track_calls("error")
    mock_logger.critical.side_effect = track_calls("critical")

    return mock_logger


# Parametrize decorators for common test scenarios
pytest_parametrize_truncation_lengths = pytest.mark.parametrize(
    "truncation_length", [25, 50, 100, 200, 500]
)

pytest_parametrize_config_variants = pytest.mark.parametrize(
    "config_name,config",
    [
        ("default", QueryTruncationConfig(100, "default_logs")),
        ("custom", QueryTruncationConfig(200, "custom_logs")),
        ("short", QueryTruncationConfig(50, "short_logs")),
        ("extended", QueryTruncationConfig(500, "extended_logs")),
    ],
)

pytest_parametrize_vector_types = pytest.mark.parametrize(
    "vector_type", ["legacy", "modern", "mixed"]
)

pytest_parametrize_error_scenarios = pytest.mark.parametrize(
    "error_type",
    ["network_timeout", "invalid_api_key", "index_not_found", "rate_limit"],
)
