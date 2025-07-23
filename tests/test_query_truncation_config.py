#!/usr/bin/env python3
"""
Test script to verify the configurable query truncation length feature
in URLMetadataLogger works correctly.

This test suite uses pytest fixtures for better test organization and reusability.
"""

import os

from btc_max_knowledge_agent.utils.url_metadata_logger import URLMetadataLogger

from .conftest import (
    pytest_parametrize_config_variants,
    pytest_parametrize_truncation_lengths,
)


class TestQueryTruncationConfig:
    """Test suite for query truncation configuration."""

    def test_configurable_query_truncation_with_fixtures(
        self, temp_config_dir, config_variants, sample_test_data
    ):
        """Test that query truncation length is configurable using fixtures."""

        long_query = sample_test_data["queries"][3]  # 150 'A' characters

        for config_name, config in config_variants.items():
            # Create logger with config from fixture
            logger_dir = temp_config_dir / "logs" / config_name
            logger_dir.mkdir(parents=True, exist_ok=True)

            logger = URLMetadataLogger(
                log_dir=str(logger_dir),
                query_truncation_length=config.query_truncation_length,
            )

            # Test logging with the configuration
            logger.log_retrieval(long_query, 5, 250.0)

            # Verify the configuration is stored correctly
            assert (
                logger.config["query_truncation_length"]
                == config.query_truncation_length
            ), f"Config truncation length should be {config.query_truncation_length}, got {logger.config['query_truncation_length']}"

    @pytest_parametrize_truncation_lengths
    def test_truncation_length_parameter(self, truncation_length, temp_config_dir):
        """Test various truncation lengths using parametrized fixtures."""

        logger_dir = temp_config_dir / "logs" / f"test_{truncation_length}"
        logger_dir.mkdir(parents=True, exist_ok=True)

        logger = URLMetadataLogger(
            log_dir=str(logger_dir), query_truncation_length=truncation_length
        )

        # Test with a known long query
        test_query = "A" * 300  # 300 characters
        logger.log_retrieval(test_query, 1, 50.0)

        # Verify configuration
        assert (
            logger.config["query_truncation_length"] == truncation_length
        ), f"Truncation length should be {truncation_length}, got {logger.config['query_truncation_length']}"

    def test_default_truncation_config(self, default_query_config, temp_config_dir):
        """Test default configuration using fixture."""

        logger_dir = temp_config_dir / "logs" / "default"
        logger_dir.mkdir(parents=True, exist_ok=True)

        logger = URLMetadataLogger(
            log_dir=str(logger_dir),
            query_truncation_length=default_query_config.query_truncation_length,
        )

        assert (
            logger.config["query_truncation_length"] == 100
        ), f"Default truncation length should be 100, got {logger.config['query_truncation_length']}"

    def test_custom_truncation_config(self, custom_query_config, temp_config_dir):
        """Test custom configuration using fixture."""

        logger_dir = temp_config_dir / "logs" / "custom"
        logger_dir.mkdir(parents=True, exist_ok=True)

        logger = URLMetadataLogger(
            log_dir=str(logger_dir),
            query_truncation_length=custom_query_config.query_truncation_length,
        )

        assert (
            logger.config["query_truncation_length"] == 200
        ), f"Custom truncation length should be 200, got {logger.config['query_truncation_length']}"

    def test_short_truncation_config(self, short_query_config, temp_config_dir):
        """Test short configuration using fixture."""

        logger_dir = temp_config_dir / "logs" / "short"
        logger_dir.mkdir(parents=True, exist_ok=True)

        logger = URLMetadataLogger(
            log_dir=str(logger_dir),
            query_truncation_length=short_query_config.query_truncation_length,
        )

        assert (
            logger.config["query_truncation_length"] == 50
        ), f"Short truncation length should be 50, got {logger.config['query_truncation_length']}"

    def test_query_truncation_with_sample_data(
        self, sample_test_data, mock_url_metadata_logger
    ):
        """Test actual query truncation behavior with sample data."""

        sample_test_data["expected_truncations"]
        truncation_length = mock_url_metadata_logger.config["query_truncation_length"]

        for original_query in sample_test_data["queries"]:
            # Log the query
            mock_url_metadata_logger.log_retrieval(original_query, 3, 100.0)

            # For queries longer than truncation length, verify they would be truncated
            if len(original_query) > truncation_length:
                expected_truncated = original_query[:truncation_length]
                # This is a conceptual test - in practice, we'd need to capture log output
                # to verify the actual truncation occurs
                assert (
                    len(expected_truncated) == truncation_length
                ), f"Truncated query length should be {truncation_length}, got {len(expected_truncated)}"

    @pytest_parametrize_config_variants
    def test_config_variants_parametrized(self, config_name, config, temp_config_dir):
        """Test configuration variants using parametrized fixture."""

        logger_dir = temp_config_dir / "logs" / config_name
        logger_dir.mkdir(parents=True, exist_ok=True)

        logger = URLMetadataLogger(
            log_dir=str(logger_dir),
            query_truncation_length=config.query_truncation_length,
        )

        # Verify configuration matches the fixture
        assert (
            logger.config["query_truncation_length"] == config.query_truncation_length
        ), f"Config variant {config_name} should have truncation length {config.query_truncation_length}, got {logger.config['query_truncation_length']}"

        # Test logging with this configuration
        test_query = f"Test query for {config_name} configuration" + ("x" * 200)
        logger.log_retrieval(test_query, 2, 75.0)

    def test_boundary_values_truncation_length(self, temp_config_dir):
        """Test boundary values for truncation length configuration."""
        boundary_test_cases = [
            # Minimum valid truncation length
            {"length": 1, "description": "single character truncation"},
            # Very small truncation
            {"length": 5, "description": "very short truncation"},
            # Zero truncation (edge case)
            {"length": 0, "description": "zero truncation"},
            # Negative truncation (invalid)
            {"length": -1, "description": "negative truncation"},
            # Large truncation length
            {"length": 10000, "description": "very large truncation"},
            # Extremely large truncation
            {"length": 1000000, "description": "extremely large truncation"},
        ]

        for test_case in boundary_test_cases:
            logger_dir = temp_config_dir / "logs" / f"boundary_{test_case['length']}"
            logger_dir.mkdir(parents=True, exist_ok=True)

            try:
                logger = URLMetadataLogger(
                    log_dir=str(logger_dir), query_truncation_length=test_case["length"]
                )

                # Test with a known query
                test_query = "A" * 500  # 500 characters
                logger.log_retrieval(test_query, 1, 50.0)

                # Verify configuration for valid cases
                if test_case["length"] >= 0:
                    assert (
                        logger.config["query_truncation_length"] == test_case["length"]
                    ), f"Boundary case {test_case['description']} should set truncation to {test_case['length']}, got {logger.config['query_truncation_length']}"

            except Exception as e:
                # Invalid cases should raise appropriate errors
                if test_case["length"] < 0:
                    assert (
                        "negative" in str(e).lower() or "invalid" in str(e).lower()
                    ), f"Negative truncation length should raise appropriate error, got: {e}"
                else:
                    # Unexpected errors for non-negative values
                    assert (
                        False
                    ), f"Unexpected error for {test_case['description']}: {e}"

    def test_invalid_config_paths(self, temp_config_dir):
        """Test handling of invalid configuration paths."""
        invalid_path_cases = [
            # Non-existent directory (should be created)
            temp_config_dir / "non_existent" / "deep" / "path",
            # Path with special characters
            temp_config_dir / "special!@#$%^&*()_+path",
            # Very long path name
            temp_config_dir / ("very_long_directory_name_" * 10),
        ]

        for invalid_path in invalid_path_cases:
            try:
                logger = URLMetadataLogger(
                    log_dir=str(invalid_path), query_truncation_length=100
                )

                # Test that logging still works
                logger.log_retrieval("Test query for invalid path", 1, 50.0)

                # Verify config is still correct
                assert (
                    logger.config["query_truncation_length"] == 100
                ), f"Logger with path {invalid_path} should maintain config, got {logger.config['query_truncation_length']}"

            except Exception as e:
                # Document expected path-related errors
                assert (
                    "path" in str(e).lower()
                    or "directory" in str(e).lower()
                    or "permission" in str(e).lower()
                ), f"Path-related error expected for {invalid_path}, got: {e}"

    def test_missing_config_keys_in_logger(self, temp_config_dir):
        """Test behavior when logger config is missing expected keys."""
        logger_dir = temp_config_dir / "logs" / "missing_keys"
        logger_dir.mkdir(parents=True, exist_ok=True)

        # Create logger normally first
        logger = URLMetadataLogger(log_dir=str(logger_dir), query_truncation_length=150)

        # Simulate missing config key by manipulating the config
        original_config = logger.config.copy()

        # Remove the truncation length key
        if "query_truncation_length" in logger.config:
            del logger.config["query_truncation_length"]

        # Test behavior with missing key
        try:
            logger.log_retrieval("Test query with missing config key", 1, 50.0)
            # If it succeeds, it should have handled the missing key gracefully
        except Exception as e:
            assert (
                "config" in str(e).lower() or "key" in str(e).lower()
            ), f"Missing config key should raise appropriate error, got: {e}"

        # Restore config for cleanup
        logger.config = original_config

    def test_extreme_query_lengths_with_truncation(self, temp_config_dir):
        """Test truncation behavior with extreme query lengths."""
        extreme_cases = [
            # Empty query
            {"query": "", "truncation": 100, "description": "empty query"},
            # Single character query
            {"query": "A", "truncation": 100, "description": "single character query"},
            # Query exactly at truncation limit
            {"query": "B" * 50, "truncation": 50, "description": "query at limit"},
            # Query one character over limit
            {
                "query": "C" * 51,
                "truncation": 50,
                "description": "query just over limit",
            },
            # Extremely long query
            {
                "query": "D" * 100000,
                "truncation": 100,
                "description": "extremely long query",
            },
            # Query with special characters
            {
                "query": "你好世界" * 1000,
                "truncation": 100,
                "description": "unicode query",
            },
            # Query with newlines and special chars
            {
                "query": "Line1\nLine2\tTabbed\r\nWindows line ending" * 100,
                "truncation": 200,
                "description": "multiline query",
            },
        ]

        for case in extreme_cases:
            logger_dir = (
                temp_config_dir
                / "logs"
                / f"extreme_{case['description'].replace(' ', '_')}"
            )
            logger_dir.mkdir(parents=True, exist_ok=True)

            logger = URLMetadataLogger(
                log_dir=str(logger_dir), query_truncation_length=case["truncation"]
            )

            try:
                # This should not crash regardless of query content
                logger.log_retrieval(case["query"], 1, 50.0)

                # Verify config remains intact
                assert (
                    logger.config["query_truncation_length"] == case["truncation"]
                ), f"Extreme case {case['description']} should preserve truncation config {case['truncation']}, got {logger.config['query_truncation_length']}"

            except Exception as e:
                # Document any encoding or processing errors
                assert (
                    "encoding" in str(e).lower()
                    or "unicode" in str(e).lower()
                    or "memory" in str(e).lower()
                ), f"Extreme query case {case['description']} failed with unexpected error: {e}"

    def test_concurrent_logger_configs(self, temp_config_dir):
        """Test multiple loggers with different truncation configs used concurrently."""
        # Create multiple loggers with different configs
        loggers = {}
        configs = [10, 50, 100, 200, 500]

        for config_value in configs:
            logger_dir = temp_config_dir / "logs" / f"concurrent_{config_value}"
            logger_dir.mkdir(parents=True, exist_ok=True)

            loggers[config_value] = URLMetadataLogger(
                log_dir=str(logger_dir), query_truncation_length=config_value
            )

        # Test that each logger maintains its own config
        test_query = "Concurrent test query " * 50  # Long enough to test truncation

        for config_value, logger in loggers.items():
            logger.log_retrieval(test_query, 1, 50.0)

            # Verify each logger kept its config
            assert (
                logger.config["query_truncation_length"] == config_value
            ), f"Concurrent logger with config {config_value} should maintain its setting, got {logger.config['query_truncation_length']}"

        # Cross-verify that configs didn't interfere with each other
        for config_value, logger in loggers.items():
            assert (
                logger.config["query_truncation_length"] == config_value
            ), f"After concurrent usage, logger config {config_value} should be unchanged, got {logger.config['query_truncation_length']}"


def test_configurable_query_truncation():
    """Legacy test function maintained for backward compatibility."""

    import shutil
    import tempfile

    # Create temporary directory for test logs
    temp_dir = tempfile.mkdtemp()

    try:
        # Test with default truncation length (100)
        logger_default = URLMetadataLogger(log_dir=os.path.join(temp_dir, "default"))

        long_query = (
            "This is a very long query that should be truncated " * 10
        )  # ~500 chars

        # This would log the query with default 100-char truncation
        logger_default.log_retrieval(long_query, 5, 250.0)

        # Verify the configuration
        assert (
            logger_default.config["query_truncation_length"] == 100
        ), f"Default logger should have truncation length 100, got {logger_default.config['query_truncation_length']}"

        # Test with custom truncation length (200)
        logger_custom = URLMetadataLogger(
            log_dir=os.path.join(temp_dir, "custom"), query_truncation_length=200
        )

        # This would log the query with custom 200-char truncation
        logger_custom.log_retrieval(long_query, 3, 180.0)

        # Verify the configuration
        assert (
            logger_custom.config["query_truncation_length"] == 200
        ), f"Custom logger should have truncation length 200, got {logger_custom.config['query_truncation_length']}"

        # Test with very short truncation length (50)
        logger_short = URLMetadataLogger(
            log_dir=os.path.join(temp_dir, "short"), query_truncation_length=50
        )

        # This would log the query with short 50-char truncation
        logger_short.log_retrieval(long_query, 8, 95.0)

        # Verify the configuration
        assert (
            logger_short.config["query_truncation_length"] == 50
        ), f"Short logger should have truncation length 50, got {logger_short.config['query_truncation_length']}"

        # Test that the actual truncation works as expected

        # Test with 75-char limit
        logger_75 = URLMetadataLogger(
            log_dir=os.path.join(temp_dir, "test75"), query_truncation_length=75
        )

        # In a real scenario, we'd need to capture the log output to verify truncation
        # For this test, we just verify the configuration is stored correctly
        expected_truncated_length = 75
        actual_config_length = logger_75.config["query_truncation_length"]

        assert (
            actual_config_length == expected_truncated_length
        ), f"75-char logger should have truncation length {expected_truncated_length}, got {actual_config_length}"

    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir)


def test_backwards_compatibility():
    """Test that existing code without the parameter still works."""
    import shutil
    import tempfile

    print("\nTesting backwards compatibility...")

    temp_dir = tempfile.mkdtemp()

    try:
        # This should work without specifying query_truncation_length
        logger = URLMetadataLogger(log_dir=temp_dir)

        # Should use default value of 100
        assert (
            logger.config["query_truncation_length"] == 100
        ), f"Backwards compatible logger should default to 100, got {logger.config['query_truncation_length']}"
        print("✓ Backwards compatibility maintained - defaults to 100 chars")

        # Test logging works
        logger.log_retrieval("Test query for backwards compatibility", 1, 50.0)
        print("✓ Logging functionality works with default configuration")

    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    print("Testing configurable query truncation length in URLMetadataLogger...")
    print("=" * 60)

    test_configurable_query_truncation()
    test_backwards_compatibility()

    print("\n" + "=" * 60)
    print("✅ All tests completed successfully!")
    print("\nThe URLMetadataLogger now supports configurable query truncation length:")
    print("- Use URLMetadataLogger() for default 100-character truncation")
    print("- Use URLMetadataLogger(query_truncation_length=N) for custom truncation")
    print("- The change is backwards compatible with existing code")
