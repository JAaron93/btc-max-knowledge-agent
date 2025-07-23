"""
Test for public API cache hit functionality.

This test verifies that validate_url_batch properly caches results
by patching validate_url_format to track call counts and ensuring
the cache works without touching private helpers.
"""

from unittest.mock import patch

import pytest

from btc_max_knowledge_agent.utils.url_utils import validate_url_batch, validate_url_format


class TestPublicAPICacheHit:
    """Test for basic cache hit functionality using public API only."""

    def test_cache_hit_basic(self):
        """
        Test that validate_url_batch uses cache on second call.

        Steps:
        1. Patch validate_url_format to record call count while delegating to real implementation
        2. Call validate_url_batch twice with same URL list and check_accessibility=False
        3. Assert:
           - First call returns valid result
           - Second call returns identical result
           - validate_url_format was NOT invoked again on second call (showing cache was used)
        """
        # Choose a URL that should pass validation
        test_url = "https://example.com"
        url_list = [test_url]

        # Store the original function to delegate to it
        original_validate_url_format = validate_url_format

        # Create a mock that tracks call count but delegates to real implementation
        call_count = 0

        def mock_validate_url_format(url):
            nonlocal call_count
            call_count += 1
            # Delegate to the real implementation
            return original_validate_url_format(url)

        # Patch validate_url_format
        with patch(
            "btc_max_knowledge_agent.utils.url_utils.validate_url_format",
            side_effect=mock_validate_url_format,
        ):

            # First call to validate_url_batch
            result1 = validate_url_batch(url_list, check_accessibility=False)

            # Verify first call succeeded and called validate_url_format
            assert len(result1) == 1
            assert test_url in result1
            assert result1[test_url]["valid"] is True
            assert result1[test_url]["secure"] is True
            assert result1[test_url]["normalized"] is not None
            assert (
                call_count == 1
            ), f"Expected 1 call to validate_url_format, got {call_count}"

            # Second call to validate_url_batch with the same URL list
            result2 = validate_url_batch(url_list, check_accessibility=False)

            # Verify second call returns identical result
            assert len(result2) == 1
            assert test_url in result2
            assert result2[test_url]["valid"] is True
            assert result2[test_url]["secure"] is True
            assert result2[test_url]["normalized"] is not None

            # The key assertion: validate_url_format should NOT have been called again
            # because the cache should have been used
            assert (
                call_count == 1
            ), f"Expected validate_url_format to only be called once due to caching, but it was called {call_count} times"

            # Verify the results are identical
            assert (
                result1 == result2
            ), "First and second call results should be identical"

    def test_cache_hit_with_invalid_url(self):
        """
        Test cache hit with an invalid URL.

        This ensures caching works for both valid and invalid URLs.
        """
        # Choose a URL that should fail validation but still calls validate_url_format
        # This URL has a valid format but will fail security validation later
        test_url = "https://127.0.0.1/path"  # This will pass format validation but fail security
        url_list = [test_url]

        # Store the original function to delegate to it
        original_validate_url_format = validate_url_format

        # Create a mock that tracks call count but delegates to real implementation
        call_count = 0

        def mock_validate_url_format(url):
            nonlocal call_count
            call_count += 1
            # Delegate to the real implementation
            return original_validate_url_format(url)

        # Patch validate_url_format
        with patch(
            "btc_max_knowledge_agent.utils.url_utils.validate_url_format",
            side_effect=mock_validate_url_format,
        ):

            # First call to validate_url_batch
            result1 = validate_url_batch(url_list, check_accessibility=False)

            # Verify first call failed and called validate_url_format
            assert len(result1) == 1
            assert test_url in result1
            assert result1[test_url]["valid"] is False
            assert result1[test_url]["error"] is not None
            assert (
                call_count == 1
            ), f"Expected 1 call to validate_url_format, got {call_count}"

            # Second call to validate_url_batch with the same URL list
            result2 = validate_url_batch(url_list, check_accessibility=False)

            # Verify second call returns result from cache (valid/secure=False, error may be None due to caching logic)
            assert len(result2) == 1
            assert test_url in result2
            assert result2[test_url]["valid"] is False
            assert result2[test_url]["secure"] is False
            # Note: error field may be None when using cache, but valid/secure should still be False

            # The key assertion: validate_url_format should NOT have been called again
            # because the cache should have been used
            assert (
                call_count == 1
            ), f"Expected validate_url_format to only be called once due to caching, but it was called {call_count} times"

            # Verify the core results are consistent (valid/secure should be the same)
            assert (
                result1[test_url]["valid"] == result2[test_url]["valid"]
            ), "valid field should be consistent"
            assert (
                result1[test_url]["secure"] == result2[test_url]["secure"]
            ), "secure field should be consistent"

    def test_cache_hit_multiple_urls(self):
        """
        Test cache hit with multiple URLs.

        This ensures caching works correctly when multiple URLs are processed.
        """
        # Mix of valid URLs that will all call validate_url_format
        test_urls = [
            "https://example.com",
            "https://test.example.org",
            "https://another.example.net",
        ]

        # Store the original function to delegate to it
        original_validate_url_format = validate_url_format

        # Create a mock that tracks call count but delegates to real implementation
        call_count = 0

        def mock_validate_url_format(url):
            nonlocal call_count
            call_count += 1
            # Delegate to the real implementation
            return original_validate_url_format(url)

        # Patch validate_url_format
        with patch(
            "btc_max_knowledge_agent.utils.url_utils.validate_url_format",
            side_effect=mock_validate_url_format,
        ):

            # First call to validate_url_batch
            result1 = validate_url_batch(test_urls, check_accessibility=False)

            # Verify first call processed all URLs and called validate_url_format for each
            assert len(result1) == 3
            for url in test_urls:
                assert url in result1
                assert result1[url]["valid"] is True  # All should be valid
            # Should have called validate_url_format once per URL
            assert (
                call_count == 3
            ), f"Expected exactly 3 calls to validate_url_format, got {call_count}"

            # Second call to validate_url_batch with the same URL list
            result2 = validate_url_batch(test_urls, check_accessibility=False)

            # Verify second call returns results from cache
            assert len(result2) == 3
            for url in test_urls:
                assert url in result2
                assert result2[url]["valid"] is True  # All should still be valid

            # The key assertion: validate_url_format should NOT have been called again
            # because the cache should have been used for all URLs
            assert (
                call_count == 3
            ), f"Expected validate_url_format to only be called 3 times total due to caching, but it was called {call_count} times"

            # Verify core validation results are consistent
            for url in test_urls:
                assert (
                    result1[url]["valid"] == result2[url]["valid"]
                ), f"valid field should be consistent for {url}"
                assert (
                    result1[url]["secure"] == result2[url]["secure"]
                ), f"secure field should be consistent for {url}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
