"""
Step 5: Add public-API test: cache hit on large batch

This test verifies that validate_url_batch properly uses cache for large batches
by patching validate_url_format to raise if called on the second batch validation.

Requirements:
1. Generate ~100 URLs
2. Call validate_url_batch(urls) once 
3. Patch validate_url_format to raise if called
4. Call validate_url_batch(urls) again and assert no exception, 
   confirming every URL came from cache without hitting validation logic
"""

import pytest
from unittest.mock import patch
from src.utils.url_utils import validate_url_batch, validate_url_format


class TestPublicAPICacheHitLargeBatch:
    """Test for cache hit functionality with large batch of URLs using only public API."""
    
    def test_large_batch_cache_hit(self):
        """
        Test that validate_url_batch properly caches results for large batches.
        
        This test:
        1. Generates ~100 valid URLs 
        2. Calls validate_url_batch once to populate cache
        3. Patches validate_url_format to raise exception if called
        4. Calls validate_url_batch again with same URLs
        5. Verifies no exception is raised (confirming all URLs came from cache)
        """
        # Generate ~100 URLs with different domains and paths
        base_domains = [
            "example.com", "test.org", "demo.net", "sample.co", "mock.io",
            "api.example.com", "cdn.test.org", "static.demo.net", "www.sample.co",
            "blog.mock.io", "docs.example.com", "help.test.org", "wiki.demo.net",
            "forum.sample.co", "news.mock.io", "shop.example.com", "mail.test.org",
            "dev.demo.net", "staging.sample.co", "beta.mock.io"
        ]
        
        url_list = []
        
        # Generate URLs with different paths to create ~100 unique URLs
        for i, domain in enumerate(base_domains):
            # Add base URL
            url_list.append(f"https://{domain}")
            
            # Add URL with path
            url_list.append(f"https://{domain}/page{i}")
            
            # Add URL with query parameters
            url_list.append(f"https://{domain}/search?q=test{i}")
            
            # Add URL with multiple path segments
            url_list.append(f"https://{domain}/api/v1/resource{i}")
            
            # Add URL with fragment
            url_list.append(f"https://{domain}/docs#section{i}")
        
        # Ensure we have ~100 URLs
        assert len(url_list) == 100, f"Expected 100 URLs, got {len(url_list)}"
        
        print(f"Generated {len(url_list)} URLs for large batch test")
        
        # First call to validate_url_batch to populate the cache
        print("First call: populating cache with all URLs...")
        result1 = validate_url_batch(url_list, check_accessibility=False)
        
        # Verify first call processed all URLs
        assert len(result1) == 100
        
        # Count how many URLs were successfully validated
        valid_count = sum(1 for result in result1.values() if result['valid'])
        print(f"First call: {valid_count} URLs validated successfully")
        
        # We expect most URLs to be valid (they're well-formed)
        assert valid_count > 90, f"Expected most URLs to be valid, got {valid_count}/100"
        
        # Store original function reference
        original_validate_url_format = validate_url_format
        
        def failing_validate_url_format(url):
            """Mock that raises exception if called - should not be called due to cache."""
            raise AssertionError(
                f"validate_url_format was called for URL '{url}' - cache should have prevented this!"
            )
        
        # Patch validate_url_format to raise if called (should not happen due to cache)
        print("Second call: patching validate_url_format to raise if called...")
        with patch('src.utils.url_utils.validate_url_format', 
                  side_effect=failing_validate_url_format):
            
            # Second call to validate_url_batch with same URL list
            # This should NOT trigger the patched function due to caching
            print("Second call: validating same URLs (should use cache)...")
            result2 = validate_url_batch(url_list, check_accessibility=False)
            
            # If we reach this point without exception, cache worked correctly
            print("Success: No exceptions raised - all URLs came from cache!")
            
            # Verify second call returns identical results
            assert len(result2) == 100
            
            # Verify the results are identical (cache returned same data)
            for url in url_list:
                assert result1[url] == result2[url], \
                    f"Cache returned different result for {url}"
            
            print("All cache results verified - test passed!")
    
    def test_large_batch_mixed_cache_states(self):
        """
        Test cache behavior with a mix of cached and uncached URLs.
        
        This test verifies that:
        1. Cached URLs don't trigger validation logic
        2. New URLs still get validated properly
        3. Mixed batches work correctly
        """
        # Start with a smaller batch to cache
        cached_urls = [
            "https://cached1.example.com",
            "https://cached2.example.com", 
            "https://cached3.example.com"
        ]
        
        # First, populate cache with these URLs
        result1 = validate_url_batch(cached_urls, check_accessibility=False)
        assert len(result1) == 3
        
        # Now create a larger batch that includes both cached and new URLs
        mixed_urls = cached_urls + [
            f"https://new{i}.example.com" for i in range(1, 8)  # 7 new URLs
        ]
        assert len(mixed_urls) == 10
        
        # Track calls to validate_url_format
        call_count = 0
        called_urls = []
        original_validate_url_format = validate_url_format
        
        def tracking_validate_url_format(url):
            """Track which URLs trigger validation logic."""
            nonlocal call_count, called_urls
            call_count += 1 
            called_urls.append(url)
            return original_validate_url_format(url)
        
        # Patch to track calls
        with patch('src.utils.url_utils.validate_url_format',
                  side_effect=tracking_validate_url_format):
            
            # Validate the mixed batch
            result2 = validate_url_batch(mixed_urls, check_accessibility=False)
            
            # Verify all URLs processed
            assert len(result2) == 10
            
            # Verify only new URLs triggered validation (not cached ones)
            assert call_count == 7, \
                f"Expected 7 calls for new URLs, got {call_count}"
            
            # Verify cached URLs were not re-validated
            for cached_url in cached_urls:
                assert cached_url not in called_urls, \
                    f"Cached URL {cached_url} should not have been re-validated"
            
            # Verify new URLs were validated
            new_urls = [url for url in mixed_urls if url not in cached_urls]
            for new_url in new_urls:
                assert new_url in called_urls, \
                    f"New URL {new_url} should have been validated"
            
            print(f"Mixed batch test passed: {len(cached_urls)} cached, {len(new_urls)} new")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
