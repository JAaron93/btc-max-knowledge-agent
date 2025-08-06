#!/usr/bin/env python3
"""
Test script to verify URL metadata functionality in upload script

Prerequisites:
    Install the package in development mode first:
    pip install -e .

    Run tests from the project root directory.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from upload_to_pinecone_assistant import _get_display_name, _is_valid_url


@pytest.fixture
def test_setup():
    """Set up test environment."""
    # Create a temporary directory for test files
    test_dir = tempfile.mkdtemp()
    upload_dir = os.path.join(test_dir, "upload_files")
    os.makedirs(upload_dir, exist_ok=True)

    # Sample test files with metadata
    test_files = {
        "bitcoin_fundamentals.txt": """# Bitcoin Fundamentals

This is a test file about Bitcoin fundamentals.

### Document Metadata
**Source URL:** https://example.com/bitcoin-fundamentals
**Original Article:** [View on Example.com](https://example.com/bitcoin-fundamentals)
**Direct Link:** [Download PDF](https://example.com/bitcoin-fundamentals.pdf)""",
        "bitcoin_news.txt": """# Bitcoin News

Latest Bitcoin news and updates.

### Document Metadata
**Source URL:** https://news.example.com/bitcoin
**Original Article:** [View on News Example](https://news.example.com/bitcoin)""",
        "bitcoin_overview.txt": """# Bitcoin Overview

A comprehensive overview of Bitcoin.

### Document Metadata
**Source URL:** https://example.com/bitcoin-overview
""",
    }

    # Create test files in the temporary directory
    for filename, content in test_files.items():
        with open(os.path.join(upload_dir, filename), "w", encoding="utf-8") as f:
            f.write(content)

    yield {"test_dir": test_dir, "upload_dir": upload_dir, "test_files": test_files}

    # Cleanup
    shutil.rmtree(test_dir, ignore_errors=True)


def test_url_validation():
    """Test URL validation function"""
    test_cases = [
        ("https://bitcoin.org/bitcoin.pdf", True),
        ("http://example.com", True),
        ("https://cointelegraph.com/news/article", True),
        ("invalid-url", False),
        ("", False),
        (None, False),
        ("ftp://example.com", False),
        ("https://", False),
        ("https://localhost:8080", True),
    ]

    for url, expected in test_cases:
        result = _is_valid_url(url)
        assert result == expected, f"URL validation failed for {url}"


def test_display_name_generation():
    """Test display name generation from URLs."""
    test_cases = [
        ("https://cointelegraph.com/rss", "Cointelegraph.Com"),
        ("https://www.coindesk.com/feed", "Coindesk.Com"),
        ("https://subdomain.example.org/page", "Subdomain.Example.Org"),
        ("bitcoin.org", "bitcoin.org"),
        ("", "View Source"),
        (None, "View Source"),
    ]

    for source, expected in test_cases:
        result = _get_display_name(source)
        assert result == expected, f"Display name generation failed for '{source}'"


def test_file_metadata_validation(test_setup):
    """Test that files contain required URL metadata."""
    upload_dir = test_setup["upload_dir"]
    test_files = test_setup["test_files"]

    for filename, expected_content in test_files.items():
        filepath = os.path.join(upload_dir, filename)

        # Verify file exists
        assert os.path.exists(filepath), (
            f"Test file {filename} was not created in {upload_dir}"
        )

        # Read file content with error handling
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for required metadata elements
            assert "### Document Metadata" in content, (
                f"File {filename} is missing the metadata section"
            )

            # Check for source URL if it's not the overview file
            if filename != "bitcoin_overview.txt":
                assert "**Source URL:**" in content, (
                    f"File {filename} is missing the Source URL field"
                )

        except UnicodeDecodeError:
            pytest.fail(f"Failed to read {filename}: Invalid UTF-8 encoding")
        except IOError as e:
            pytest.fail(f"Failed to read {filename}: {str(e)}")


@patch("os.listdir")
@patch("os.path.getsize")
def test_file_reading_error_handling(mock_getsize, mock_listdir):
    """Test error handling when file operations fail in upload script."""
    from upload_to_pinecone_assistant import create_upload_files

    # Configure mocks to raise IOError to simulate file system issues
    mock_listdir.side_effect = IOError("Permission denied")
    mock_getsize.side_effect = IOError("File not accessible")

    # Mock the BitcoinDataCollector to avoid external dependencies
    with patch("upload_to_pinecone_assistant.BitcoinDataCollector") as mock_collector:
        mock_collector.return_value.collect_all_documents.return_value = [
            {
                "title": "Test Document",
                "content": "Test content",
                "source": "test",
                "category": "test",
                "url": "https://example.com",
            }
        ]

        # Test that IOError is raised when file system operations fail
        with pytest.raises(IOError, match="Permission denied"):
            create_upload_files()


def test_temporary_directory_isolation(test_setup):
    """Ensure tests are isolated by using temporary directories."""
    test_dir = test_setup["test_dir"]
    upload_dir = test_setup["upload_dir"]

    # Verify our test directory is not the production directory
    assert "data/upload_files" not in upload_dir
    assert upload_dir.startswith(test_dir)


if __name__ == "__main__":
    pytest.main([__file__])
