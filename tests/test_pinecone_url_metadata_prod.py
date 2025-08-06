#!/usr/bin/env python3
"""
Production test script to verify URL metadata handling in PineconeClient
when ALLOW_LOCALHOST_URLS=False.

This test module runs only when localhost URLs should be rejected,
which is the default production behavior.
"""

import importlib
import os
import sys
import unittest
from unittest.mock import Mock, patch

# Path setupoject root to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.retrieval.pinecone_client import PineconeClient


class TestPineconeURLMetadataProduction(unittest.TestCase):
    """
    Test URL validation behavior in production mode where localhost URLs are rejected.

    This test class specifically validates that localhost URLs are properly rejected
    when ALLOW_LOCALHOST_URLS is False (the default production setting).
    """

    @staticmethod
    def _setup_environment_patch(env_vars):
        """Set up environment variable patching.

        Args:
            env_vars: Dictionary of environment variables to patch

        Returns:
            patch object that can be started/stopped
        """
        return patch.dict(os.environ, env_vars, clear=False)

    @staticmethod
    def _reload_config_modules():
        """Reload configuration modules to pick up new environment variables.

        This method gracefully handles module reloading with error handling.
        """
        modules_to_reload = [
            "src.utils.config",
            "utils.config",
            "src.utils.url_utils",
            "utils.url_utils",
        ]

        for module_name in modules_to_reload:
            if module_name in sys.modules:
                try:
                    importlib.reload(sys.modules[module_name])
                except Exception as e:
                    # Log the error but don't fail the test setup
                    print(f"Warning: Failed to reload {module_name}: {e}")

    def setUp(self):
        """Set up test fixtures with production-like settings"""
        # Mock environment variables for Config with production settings
        test_env_vars = {
            "PINECONE_API_KEY": "test-key",
            "PINECONE_INDEX_NAME": "test-index",
            "EMBEDDING_DIMENSION": "768",
            "ALLOW_LOCALHOST_URLS": (
                "False"
            ),  # Production setting - reject localhost URLs
        }

        # Set up environment patching
        self.env_patcher = self._setup_environment_patch(test_env_vars)
        self.env_patcher.start()

        # Reload config modules to pick up new environment variables
        self._reload_config_modules()

        # Mock the external dependencies
        try:
            with patch("src.retrieval.pinecone_client.Pinecone"):
                self.client = PineconeClient()
        except Exception as e:
            self.fail(f"Failed to initialize PineconeClient: {e}")

    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self, "env_patcher"):
            self.env_patcher.stop()

    def test_validate_and_sanitize_url_localhost_rejected(self):
        """Test that localhost URLs are rejected when ALLOW_LOCALHOST_URLS=False"""
        # Ensure environment is correctly set for this test
        os.environ["ALLOW_LOCALHOST_URLS"] = "False"

        # Use helper method to reload config modules
        self._reload_config_modules()

        # Verify config is now False
        # NOTE: setup_src_path() is now called once in conftest.py
        try:
            from utils.config import Config

            assert (
                Config.ALLOW_LOCALHOST_URLS is False
            ), "Config should have ALLOW_LOCALHOST_URLS=False"
        except ImportError as e:
            self.fail(f"Failed to import Config: {e}")

        localhost_urls = [
            "http://localhost",
            "https://localhost",
            "http://localhost:8080",
            "https://localhost:3000",
            "http://localhost/path",
            "https://localhost/path?query=value",
            "http://*********",
            "https://*********:8080",
            "http://*********/api/v1",
        ]

        for url in localhost_urls:
            result = self.client.validate_and_sanitize_url(url)
            assert (
                result is None
            ), f"Localhost URL {url} should be rejected when ALLOW_LOCALHOST_URLS=False, got {result}"

    def test_validate_and_sanitize_url_production_valid_urls(self):
        """Test that normal URLs still work in production mode"""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://subdomain.example.com",
            "https://example.com/path",
            "https://example.com/path?query=value",
            "https://api.github.com/users",
            "http://bitcoin.org/bitcoin.pdf",
        ]

        for url in valid_urls:
            result = self.client.validate_and_sanitize_url(url)
            assert (
                result == url
            ), f"Valid URL {url} should work in production mode, got {result}"

    def test_upsert_documents_handles_localhost_urls_gracefully(self):
        """Test that documents with localhost URLs are handled gracefully in production

        URL Replacement Strategy:
        When ALLOW_LOCALHOST_URLS=False, rejected localhost URLs are handled as follows:

        1. Real Implementation (src/retrieval/pinecone_client.py):
           - Uses FallbackURLStrategy.placeholder_url(doc_id) from url_error_handler.py
           - Returns URLs in format: "https://placeholder.local/{doc_id}"
           - Example: "http://localhost:8080" -> "https://placeholder.local/doc1"

        2. Stub Implementation (src/btc_max_knowledge_agent/retrieval/pinecone_client.py):
           - validate_and_sanitize_url() returns None for rejected URLs
           - upsert_documents() uses empty string ("") for None URLs
           - Example: "http://localhost:8080" -> ""

        This test validates both implementations by accepting either placeholder URLs
        or empty strings, ensuring compatibility with both code paths.
        """
        # Mock the index
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)

        # Test documents with localhost URLs that should be rejected
        documents = [
            {
                "id": "doc1",
                "title": "Test Document 1",
                "content": "This is test content 1",
                "source": "Test Source 1",
                "category": "test",
                "url": "http://localhost:8080/api",  # Should be rejected
                "embedding": [0.1] * 768,
            },
            {
                "id": "doc2",
                "title": "Test Document 2",
                "content": "This is test content 2",
                "source": "Test Source 2",
                "category": "test",
                "url": "https://example.com/doc2",  # Should be accepted
                "embedding": [0.2] * 768,
            },
            {
                "id": "doc3",
                "title": "Test Document 3",
                "content": "This is test content 3",
                "source": "Test Source 3",
                "category": "test",
                "url": "https://127.0.0.1/local-api",  # Should be rejected
                "embedding": [0.3] * 768,
            },
        ]

        # This should not raise an exception even with localhost URLs
        try:
            self.client.upsert_documents(documents)
        except Exception as e:
            self.fail(f"upsert_documents raised an exception with localhost URLs: {e}")

        # Verify upsert was called
        mock_index.upsert.assert_called_once()

        # Get the vectors that were upserted
        call_args = mock_index.upsert.call_args[1]["vectors"]

        # Verify localhost URLs were rejected and replaced with placeholder URLs
        # The real implementation uses FallbackURLStrategy.placeholder_url() which returns
        # URLs in the format "https://placeholder.local/{doc_id}"

        # Document 1 (localhost) should have placeholder URL
        doc1_url = call_args[0]["metadata"]["url"]
        assert (
            doc1_url == "https://placeholder.local/doc1" or doc1_url == ""
        ), f"Localhost URL should be replaced with placeholder or empty, got {doc1_url}"

        # Document 2 (valid URL) should be unchanged
        assert (
            call_args[1]["metadata"]["url"] == "https://example.com/doc2"
        ), "Valid URL should be preserved"

        # Document 3 (localhost IP) should have placeholder URL
        doc3_url = call_args[2]["metadata"]["url"]
        assert (
            doc3_url == "https://placeholder.local/doc3" or doc3_url == ""
        ), f"Localhost IP URL should be replaced with placeholder or empty, got {doc3_url}"

    def test_production_security_validation(self):
        """Test that production security validations work correctly"""
        # Test various security-problematic URLs that should be rejected
        security_test_urls = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "file:///etc/passwd",
            "ftp://internal-server/files",
            "http://192.168.1.1/admin",  # Private IP
            "https://10.0.0.1/config",  # Private IP
            "http://172.16.0.1/api",  # Private IP
        ]

        for url in security_test_urls:
            result = self.client.validate_and_sanitize_url(url)
            assert (
                result is None
            ), f"Security-problematic URL {url} should be rejected, got {result}"

    def test_config_flag_behavior(self):
        """Test that the ALLOW_LOCALHOST_URLS flag is properly respected"""
        # This test verifies that our production test setup actually has the flag set to False
        from src.utils.config import Config

        # In this test environment, the flag should be False
        assert (
            Config.ALLOW_LOCALHOST_URLS is False
        ), "ALLOW_LOCALHOST_URLS should be False in production test environment"

    def test_localhost_domain_variations(self):
        """Test various localhost domain variations are all rejected"""
        localhost_variations = [
            "http://localhost",
            "https://localhost",
            "http://LOCALHOST",  # Case variations
            "https://LocalHost",
            "http://localhost.localdomain",
            "https://localhost.local",
        ]

        for url in localhost_variations:
            result = self.client.validate_and_sanitize_url(url)
            assert (
                result is None
            ), f"Localhost variation {url} should be rejected, got {result}"


def main():
    """Run the production tests"""
    print("🏭 Testing Pinecone URL Metadata Functionality - Production Mode")
    print("=" * 60)
    print("🚫 ALLOW_LOCALHOST_URLS=False - Localhost URLs should be rejected")
    print("=" * 60)

    # Check if we should skip these tests based on environment
    if os.getenv("ALLOW_LOCALHOST_URLS", "False").lower() == "true":
        print("⚠️  Skipping production tests - ALLOW_LOCALHOST_URLS is enabled")
        print(
            "   Set ALLOW_LOCALHOST_URLS=False to run production URL validation tests"
        )
        return

    # Run the unit tests
    unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
