#!/usr/bin/env python3
"""
Unit tests for the build_upload_payload function in PineconeAssistantAgent.

Tests payload structure validation and null-safe metadata handling.
"""

import hashlib
import os
import unittest
from unittest.mock import Mock, patch

import pytest

# Using proper absolute imports with editable package installation (pip install -e ".[dev]")
# This eliminates the need for sys.path manipulation and provides better IDE support
from src.agents.pinecone_assistant_agent import PineconeAssistantAgent


class TestBuildUploadPayload(unittest.TestCase):
    """Test cases for the build_upload_payload function"""

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

    def test_build_upload_payload_with_complete_document(self):
        """Test payload construction with a complete document including all fields"""
        doc = {
            "id": "test-doc-1",
            "content": "This is test content for the document.",
            "title": "Test Document",
            "source": "test-source.com",
            "category": "test",
            "url": "https://example.com/test-doc",
            "published": "2024-01-01",
        }

        result = self.agent.build_upload_payload(doc)

        # Verify payload structure
        self.assertIn("id", result)
        self.assertIn("text", result)
        self.assertIn("metadata", result)

        # Verify content mapping
        self.assertEqual(result["id"], "test-doc-1")
        self.assertEqual(result["text"], "This is test content for the document.")

        # Verify metadata structure
        metadata = result["metadata"]
        self.assertEqual(metadata["title"], "Test Document")
        self.assertEqual(metadata["source"], "test-source.com")
        self.assertEqual(metadata["category"], "test")
        self.assertEqual(metadata["url"], "https://example.com/test-doc")
        self.assertEqual(metadata["published"], "2024-01-01")

    def test_build_upload_payload_with_minimal_document(self):
        """Test payload construction with minimal required fields only"""
        doc = {"id": "minimal-doc", "content": "Minimal content"}

        result = self.agent.build_upload_payload(doc)

        # Verify payload structure
        self.assertIn("id", result)
        self.assertIn("text", result)
        self.assertIn("metadata", result)

        # Verify content mapping
        self.assertEqual(result["id"], "minimal-doc")
        self.assertEqual(result["text"], "Minimal content")

        # Verify metadata has safe defaults
        metadata = result["metadata"]
        self.assertEqual(metadata["title"], "")
        self.assertEqual(metadata["source"], "")
        self.assertEqual(metadata["category"], "")
        self.assertEqual(metadata["url"], "")
        self.assertEqual(metadata["published"], "")

    def test_build_upload_payload_null_safe_metadata_handling(self):
        """Test that null/None values in metadata are handled safely"""
        doc = {
            "id": "null-test-doc",
            "content": "Content with null metadata",
            "title": None,
            "source": None,
            "category": None,
            "url": None,
            "published": None,
        }

        result = self.agent.build_upload_payload(doc)

        # Verify that None values are converted to empty strings
        metadata = result["metadata"]
        for field in ["title", "source", "category", "url", "published"]:
            self.assertEqual(
                metadata[field], "", f"Field {field} should be empty string, not None"
            )

    def test_build_upload_payload_with_invalid_url(self):
        """Test payload construction with invalid URL"""
        doc = {
            "id": "invalid-url-doc",
            "content": "Document with invalid URL",
            "title": "Invalid URL Test",
            "url": "not-a-valid-url",
        }

        result = self.agent.build_upload_payload(doc)

        # URL should be empty string due to validation failure
        self.assertEqual(result["metadata"]["url"], "")

        # Other fields should still be processed correctly
        self.assertEqual(result["metadata"]["title"], "Invalid URL Test")

    def test_build_upload_payload_with_url_missing_protocol(self):
        """Test payload construction with URL missing protocol"""
        doc = {
            "id": "no-protocol-doc",
            "content": "Document with URL missing protocol",
            "title": "No Protocol Test",
            "url": "example.com/test",
        }

        result = self.agent.build_upload_payload(doc)

        # URL should be sanitized with https:// prefix
        self.assertEqual(result["metadata"]["url"], "https://example.com/test")

    def test_build_upload_payload_with_empty_strings(self):
        """Test payload construction with empty string values"""
        doc = {
            "id": "empty-strings-doc",
            "content": "Content with empty strings",
            "title": "",
            "source": "",
            "category": "",
            "url": "",
            "published": "",
        }

        result = self.agent.build_upload_payload(doc)

        # Empty strings should remain as empty strings
        metadata = result["metadata"]
        for field in ["title", "source", "category", "url", "published"]:
            self.assertEqual(metadata[field], "")

    def test_build_upload_payload_missing_required_field_id(self):
        """Test that missing 'id' field raises ValueError"""
        doc = {"content": "Content without ID"}

        with self.assertRaises(ValueError) as context:
            self.agent.build_upload_payload(doc)

        self.assertIn("missing required field 'id'", str(context.exception))

    def test_build_upload_payload_missing_required_field_content(self):
        """Test that missing 'content' field raises ValueError"""
        doc = {"id": "no-content-doc"}

        with self.assertRaises(ValueError) as context:
            self.agent.build_upload_payload(doc)

        self.assertIn("missing required field 'content'", str(context.exception))

    def test_build_upload_payload_none_document(self):
        """Test that None document raises ValueError"""
        with self.assertRaises(ValueError) as context:
            self.agent.build_upload_payload(None)

        self.assertEqual(str(context.exception), "Document cannot be None")

    def test_build_upload_payload_non_dict_document(self):
        """Test that non-dictionary document raises ValueError"""
        with self.assertRaises(ValueError) as context:
            self.agent.build_upload_payload("not-a-dict")

        self.assertEqual(str(context.exception), "Document must be a dictionary")

    def test_build_upload_payload_with_special_characters(self):
        """Test payload construction with special characters in content"""
        doc = {
            "id": "special-chars-doc",
            "content": "Content with special chars: üñíçödé, emojis 🚀, and symbols @#$%",
            "title": "Special Characters Test: éñ español",
            "source": "test-üñíçödé.com",
            "url": "https://example.com/spëcîál-pàth",
        }

        result = self.agent.build_upload_payload(doc)

        # Special characters should be preserved
        self.assertEqual(
            result["text"],
            "Content with special chars: üñíçödé, emojis 🚀, and symbols @#$%",
        )
        self.assertEqual(
            result["metadata"]["title"], "Special Characters Test: éñ español"
        )
        self.assertEqual(result["metadata"]["source"], "test-üñíçödé.com")

    def test_build_upload_payload_with_long_content(self):
        """Test payload construction with very long content"""
        long_content = "Lorem ipsum dolor sit amet. " * 1000  # Very long text
        doc = {
            "id": "long-content-doc",
            "content": long_content,
            "title": "Long Content Test",
        }

        result = self.agent.build_upload_payload(doc)

        # Long content should be preserved as-is
        self.assertEqual(result["text"], long_content)
        self.assertEqual(len(result["text"]), len(long_content))

    def test_build_upload_payload_url_validation_edge_cases(self):
        """Test URL validation with various edge cases"""
        test_cases = [
            ("http://localhost", ""),  # localhost should be rejected
            (
                "https://example.com/",
                "https://example.com/",
            ),  # trailing slash preserved
            ("example.com", "https://example.com"),  # protocol added
            ("ftp://example.com", ""),  # wrong protocol rejected
            ("https://", ""),  # incomplete URL rejected
            ("javascript:alert('xss')", ""),  # dangerous URL rejected
        ]

        for input_url, expected_url in test_cases:
            doc = {
                # Stable, reproducible id
                "id": f"url-test-{hashlib.md5(input_url.encode()).hexdigest()}",
                "content": "URL test content",
                "url": input_url,
            }

            result = self.agent.build_upload_payload(doc)
            self.assertEqual(
                result["metadata"]["url"],
                expected_url,
                f"URL '{input_url}' should validate to '{expected_url}'",
            )

    @patch("agents.pinecone_assistant_agent.logger")
    def test_build_upload_payload_logs_url_validation_failures(self, mock_logger):
        """Test that URL validation failures are logged appropriately"""
        doc = {
            "id": "logging-test-doc",
            "content": "Test content",
            "url": "invalid-url-format",
        }

        result = self.agent.build_upload_payload(doc)

        # Should log warning about URL validation failure
        mock_logger.warning.assert_called()
        self.assertIn("URL validation failed", str(mock_logger.warning.call_args))

        # URL should be empty in result
        self.assertEqual(result["metadata"]["url"], "")

    def test_build_upload_payload_metadata_structure_consistency(self):
        """Test that metadata structure is consistent across different inputs"""
        test_docs = [
            {"id": "doc1", "content": "Content 1"},
            {"id": "doc2", "content": "Content 2", "title": "Title 2"},
            {"id": "doc3", "content": "Content 3", "url": "https://example.com"},
            {
                "id": "doc4",
                "content": "Content 4",
                "title": "Title 4",
                "source": "Source 4",
                "category": "Category 4",
                "url": "https://example.com/4",
                "published": "2024-01-01",
            },
        ]

        required_metadata_fields = ["title", "source", "category", "url", "published"]

        for doc in test_docs:
            result = self.agent.build_upload_payload(doc)

            # All results should have the same metadata structure
            self.assertIn("metadata", result)
            for field in required_metadata_fields:
                self.assertIn(
                    field,
                    result["metadata"],
                    f"Field '{field}' missing in metadata for doc {doc['id']}",
                )
                # All fields should be strings (not None)
                self.assertIsInstance(
                    result["metadata"][field],
                    str,
                    f"Field '{field}' should be string, got {type(result['metadata'][field])}",
                )


class TestBuildUploadPayloadIntegration(unittest.TestCase):
    """Integration tests for build_upload_payload with other components"""

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

    def test_build_upload_payload_with_data_collector_format(self):
        """Test that payload works with realistic data from BitcoinDataCollector"""
        # Simulate document format from data collector
        doc = {
            "id": "bitcoin_whitepaper",
            "title": "Bitcoin: A Peer-to-Peer Electronic Cash System",
            "content": "Abstract. A purely peer-to-peer version of electronic cash would allow online payments to be sent directly from one party to another without going through a financial institution.",
            "source": "bitcoin.org",
            "category": "fundamentals",
            "url": "https://bitcoin.org/bitcoin.pdf",
            "published": "2008-10-31",
        }

        result = self.agent.build_upload_payload(doc)

        # Verify the payload matches expected Pinecone format
        expected_structure = {"id": str, "text": str, "metadata": dict}

        for field, expected_type in expected_structure.items():
            self.assertIn(field, result)
            self.assertIsInstance(result[field], expected_type)

        # Verify metadata completeness
        metadata = result["metadata"]
        self.assertTrue(
            all(isinstance(v, str) for v in metadata.values()),
            "All metadata values should be strings",
        )
