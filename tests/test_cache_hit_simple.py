"""
Simple test for public API cache hit functionality.

This test verifies that validate_url_batch properly caches results
by patching validate_url_format to track call counts and ensuring
the cache works without touching private helpers.
"""

from unittest.mock import patch

from btc_max_knowledge_agent.utils.url_utils import validate_url_batch, validate_url_format


def test_cache_hit_basic():
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
        "btc_max_knowledge_agent.utils.url_utils.validate_url_format", side_effect=mock_validate_url_format
    ):

        print("=== First call to validate_url_batch ===")
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

        # Second call to validate_url_batch with same URL list
        result2 = validate_url_batch(url_list, check_accessibility=False)

        # Verify second call succeeded and used cache
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
        assert result1 == result2, "First and second call results should be identical"


if __name__ == "__main__":
    test_cache_hit_basic()
