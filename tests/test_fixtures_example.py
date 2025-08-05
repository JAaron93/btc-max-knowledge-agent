#!/usr/bin/env python3
"""
Example test demonstrating the usage of new pytest fixtures for URL metadata logging.

This file showcases how to effectively use the fixtures defined in conftest.py
to write clean, reusable tests for query truncation configuration.
"""

import json

import pytest

from btc_max_knowledge_agent.utils.url_metadata_logger import URLMetadataLogger

from .conftest import (pytest_parametrize_config_variants,
                       pytest_parametrize_truncation_lengths)


class TestFixturesExample:
    """Example test class demonstrating fixture usage patterns."""

    def test_temp_config_dir_usage(self, temp_config_dir):
        """Example of using the temp_config_dir fixture."""

        # The fixture provides a temporary directory with pre-created config files
        config_dir = temp_config_dir / "config"

        # Verify the config files were created
        assert (config_dir / "basic_config.json").exists()
        assert (config_dir / "custom_config.json").exists()
        assert (config_dir / "minimal_config.json").exists()

        # Read and validate a config file
        with open(config_dir / "basic_config.json") as f:
            config = json.load(f)
            assert config["query_truncation_length"] == 100
            assert "alert_thresholds" in config

    def test_query_config_fixtures(
        self, default_query_config, custom_query_config, short_query_config
    ):
        """Example of using multiple config fixtures in one test."""

        # Test different configuration objects
        assert default_query_config.query_truncation_length == 100
        assert custom_query_config.query_truncation_length == 200
        assert short_query_config.query_truncation_length == 50

        # Convert to dict format for testing
        default_dict = default_query_config.to_dict()
        assert "query_truncation_length" in default_dict
        assert "log_dir" in default_dict

    def test_config_variants_fixture(self, config_variants):
        """Example of using the config_variants fixture for comprehensive testing."""

        # Test that all expected variants are present
        expected_variants = ["default", "custom", "short", "extended", "minimal"]
        assert all(variant in config_variants for variant in expected_variants)

        # Test properties of each variant
        assert config_variants["default"].query_truncation_length == 100
        assert config_variants["extended"].query_truncation_length == 500
        assert config_variants["minimal"].query_truncation_length == 25

    def test_sample_test_data_fixture(self, sample_test_data):
        """Example of using the sample_test_data fixture."""

        # Verify sample data structure
        assert "urls" in sample_test_data
        assert "queries" in sample_test_data
        assert "metadata" in sample_test_data
        assert "expected_truncations" in sample_test_data

        # Test with sample URLs
        urls = sample_test_data["urls"]
        assert len(urls) > 0
        assert all(url.startswith("https://") for url in urls)

        # Test with sample queries
        queries = sample_test_data["queries"]
        assert len(queries) > 0

        # Test expected truncations
        truncations = sample_test_data["expected_truncations"]
        assert 50 in truncations
        assert 100 in truncations
        assert 200 in truncations

    def test_mock_logger_fixture(self, mock_url_metadata_logger, sample_test_data):
        """Example of using the mock_url_metadata_logger fixture."""

        # The fixture provides a real URLMetadataLogger with temporary directory
        assert mock_url_metadata_logger.config["query_truncation_length"] == 100

        # Test logging operations
        test_query = sample_test_data["queries"][0]
        mock_url_metadata_logger.log_retrieval(test_query, 5, 120.5)

        # Test with different operations
        mock_url_metadata_logger.log_validation(
            sample_test_data["urls"][0], True, "secure_url", duration_ms=50.0
        )

    @pytest_parametrize_truncation_lengths
    def test_parametrized_truncation_lengths(self, truncation_length, temp_config_dir):
        """Example of using parametrized truncation lengths."""

        # This test will run multiple times with different truncation lengths
        logger_dir = temp_config_dir / "logs" / f"param_test_{truncation_length}"
        logger_dir.mkdir(parents=True, exist_ok=True)

        logger = URLMetadataLogger(
            log_dir=str(logger_dir), query_truncation_length=truncation_length
        )

        # Test that the logger was configured correctly
        assert logger.config["query_truncation_length"] == truncation_length

        # Test with a long query
        long_query = "Testing parametrized truncation lengths " * 20
        logger.log_retrieval(long_query, 3, 85.0)

    @pytest_parametrize_config_variants
    def test_parametrized_config_variants(self, config_name, config, temp_config_dir):
        """Example of using parametrized config variants."""

        # This test will run for each config variant
        logger_dir = temp_config_dir / "logs" / f"variant_{config_name}"
        logger_dir.mkdir(parents=True, exist_ok=True)

        logger = URLMetadataLogger(
            log_dir=str(logger_dir),
            query_truncation_length=config.query_truncation_length,
        )

        # Verify the configuration
        assert (
            logger.config["query_truncation_length"] == config.query_truncation_length
        )

        # Test specific behavior for each variant
        test_query = f"Testing {config_name} configuration with query truncation"
        if config_name == "extended":
            # Extended config should handle very long queries
            test_query = test_query + " with additional very long text" * 10

        logger.log_retrieval(test_query, 2, 75.0)

    def test_combined_fixtures(
        self, temp_config_dir, config_variants, sample_test_data, session_temp_dir
    ):
        """Example of combining multiple fixtures in one test."""

        # Use sample data to test each configuration variant
        for config_name, config in config_variants.items():
            logger_dir = temp_config_dir / "logs" / f"combined_{config_name}"
            logger_dir.mkdir(parents=True, exist_ok=True)

            logger = URLMetadataLogger(
                log_dir=str(logger_dir),
                query_truncation_length=config.query_truncation_length,
            )

            # Test with each sample query
            for query in sample_test_data["queries"]:
                logger.log_retrieval(query, 1, 100.0)

            # Test with each sample URL for validation
            for url in sample_test_data["urls"]:
                logger.log_validation(url, True, "test_validation", duration_ms=25.0)

        # Use session temp dir for expensive operations that could be shared
        shared_file = session_temp_dir / "shared_test_results.json"
        with open(shared_file, "w") as f:
            json.dump({"test": "combined_fixtures_completed"}, f)

        assert shared_file.exists()


class TestRealWorldScenarios:
    """Real-world scenario tests using the fixtures."""

    def test_config_loading_from_file(self, temp_config_dir):
        """Test loading configuration from the provided config files."""

        config_dir = temp_config_dir / "config"

        # Load basic config
        with open(config_dir / "basic_config.json") as f:
            basic_config = json.load(f)

        logger = URLMetadataLogger(
            log_dir=str(temp_config_dir / "logs" / "from_file"),
            query_truncation_length=basic_config["query_truncation_length"],
        )

        assert logger.config["query_truncation_length"] == 100

    def test_migration_scenario(self, temp_config_dir, config_variants):
        """Test a migration scenario from old to new configuration."""

        # Simulate old configuration (no truncation length specified)
        old_logger_dir = temp_config_dir / "logs" / "old_style"
        old_logger_dir.mkdir(parents=True, exist_ok=True)

        old_logger = URLMetadataLogger(log_dir=str(old_logger_dir))
        assert old_logger.config["query_truncation_length"] == 100  # Default

        # Simulate new configuration with custom settings
        new_config = config_variants["custom"]
        new_logger_dir = temp_config_dir / "logs" / "new_style"
        new_logger_dir.mkdir(parents=True, exist_ok=True)

        new_logger = URLMetadataLogger(
            log_dir=str(new_logger_dir),
            query_truncation_length=new_config.query_truncation_length,
        )
        assert new_logger.config["query_truncation_length"] == 200

    def test_performance_comparison(self, config_variants, sample_test_data, tmp_path):
        """Test performance implications of different truncation lengths."""

        import time

        results = {}

        for config_name, config in config_variants.items():
            # Use pytest's tmp_path fixture
            temp_dir = tmp_path / f"perf_test_{config_name}"
            temp_dir.mkdir(exist_ok=True)

            logger = URLMetadataLogger(
                log_dir=str(temp_dir),
                query_truncation_length=config.query_truncation_length,
            )

            # Measure time for logging operations
            start_time = time.time()

            for query in sample_test_data["queries"]:
                logger.log_retrieval(query, 1, 50.0)

            end_time = time.time()
            results[config_name] = end_time - start_time

        # Verify that all configurations completed successfully
        assert len(results) == len(config_variants)
        assert all(time_taken >= 0 for time_taken in results.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
