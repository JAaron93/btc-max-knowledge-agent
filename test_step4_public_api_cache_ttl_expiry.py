"""
Step 4: Add public-API test: cache TTL expiry

This test verifies that validate_url_batch respects the CACHE_TTL setting by:
1. Patching validate_url_format to track calls while delegating to real implementation
2. Calling validate_url_batch([url]) once to populate cache
3. Using patch('time.time', ...) to advance time by CACHE_TTL + 1
4. Calling validate_url_batch([url]) again 
5. Asserting the patched validate_url_format *was* invoked the second time, 
   demonstrating cache expiration via the public function

Requirements:
- Use only public API functions (validate_url_batch, validate_url_format)
- Mock time.time to simulate time advancement
- Verify cache expiry forces re-validation
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from src.utils.url_utils import validate_url_batch, validate_url_format, CACHE_TTL


class TestPublicAPICacheTTLExpiry:
    """Test for cache TTL expiry functionality using only public API."""
    
    def test_cache_ttl_expiry(self):
        """
        Test that validate_url_batch cache expires after CACHE_TTL seconds.
        
        This test:
        1. Patches validate_url_format to track calls while delegating to real implementation
        2. Calls validate_url_batch once to populate cache
        3. Uses patch('time.time', ...) to advance time by CACHE_TTL + 1 seconds
        4. Calls validate_url_batch again with the same URL
        5. Verifies that validate_url_format was called again on second call (cache expired)
        """
        # Test URL that should pass all validation
        test_url = "https://example.com"
        url_list = [test_url]
        
        # Store original function for delegation
        original_validate_url_format = validate_url_format
        
        # Track call count
        call_count = 0
        
        def mock_validate_url_format(url):
            """Mock that delegates to real implementation but tracks calls."""
            nonlocal call_count
            call_count += 1
            print(f"validate_url_format called with: {url} (call #{call_count})")
            return original_validate_url_format(url)
        
        # Get current time to simulate time advancement
        initial_time = time.time()
        
        # Patch validate_url_format to track calls
        with patch('src.utils.url_utils.validate_url_format', 
                  side_effect=mock_validate_url_format) as mock_func:
            
            print("=== First call to validate_url_batch (populate cache) ===")
            # First call to validate_url_batch to populate cache
            result1 = validate_url_batch(url_list, check_accessibility=False)
            
            # Verify first call returns valid result and called validate_url_format
            assert len(result1) == 1
            assert test_url in result1
            assert result1[test_url]['valid'] is True
            assert result1[test_url]['secure'] is True
            assert result1[test_url]['normalized'] is not None
            assert result1[test_url]['error'] is None
            assert call_count == 1, f"Expected 1 call to validate_url_format, got {call_count}"
            
            print(f"First call result: {result1[test_url]}")
            print(f"Call count after first call: {call_count}")
            print(f"CACHE_TTL is set to: {CACHE_TTL} seconds")
            
            # Now simulate time advancement by patching time.time
            # We advance time by CACHE_TTL + 1 to ensure cache expires
            advanced_time = initial_time + CACHE_TTL + 1
            
            print(f"=== Advancing time by {CACHE_TTL + 1} seconds ===")
            print(f"Original time: {initial_time}")
            print(f"Advanced time: {advanced_time}")
            
            # Patch time.time to return the advanced time
            # We need to patch the time module as imported in url_utils
            with patch('src.utils.url_utils.time.time', return_value=advanced_time):
                print("=== Second call to validate_url_batch (after cache expiry) ===")
                # Second call to validate_url_batch with the same URL list
                result2 = validate_url_batch(url_list, check_accessibility=False)
                
                # Verify second call returns identical result
                assert len(result2) == 1
                assert test_url in result2
                assert result2[test_url]['valid'] is True
                assert result2[test_url]['secure'] is True
                assert result2[test_url]['normalized'] is not None
                assert result2[test_url]['error'] is None
                
                print(f"Second call result: {result2[test_url]}")
                print(f"Call count after second call: {call_count}")
                
                # KEY ASSERTION: validate_url_format SHOULD have been called again
                # because the cache should have expired
                assert call_count == 2, \
                    f"Expected validate_url_format to be called twice due to cache expiry, " \
                    f"but it was called {call_count} times"
                
                # Verify the results are still identical (same validation logic)
                assert result1[test_url]['valid'] == result2[test_url]['valid']
                assert result1[test_url]['secure'] == result2[test_url]['secure']
                assert result1[test_url]['normalized'] == result2[test_url]['normalized']
                
                print("✓ Cache TTL expiry test passed!")
    
    def test_cache_ttl_not_expired(self):
        """
        Test that validate_url_batch cache does NOT expire before CACHE_TTL seconds.
        
        This test verifies that when time advancement is less than CACHE_TTL,
        the cache is still valid and validate_url_format is not called again.
        """
        # Test URL that should pass all validation
        test_url = "https://example.org"
        url_list = [test_url]
        
        # Store original function for delegation
        original_validate_url_format = validate_url_format
        
        # Track call count
        call_count = 0
        
        def mock_validate_url_format(url):
            """Mock that delegates to real implementation but tracks calls."""
            nonlocal call_count
            call_count += 1
            print(f"validate_url_format called with: {url} (call #{call_count})")
            return original_validate_url_format(url)
        
        # Get current time to simulate time advancement
        initial_time = time.time()
        
        # Patch validate_url_format to track calls
        with patch('src.utils.url_utils.validate_url_format', 
                  side_effect=mock_validate_url_format) as mock_func:
            
            print("=== First call to validate_url_batch (populate cache) ===")
            # First call to validate_url_batch to populate cache
            result1 = validate_url_batch(url_list, check_accessibility=False)
            
            # Verify first call returns valid result and called validate_url_format
            assert len(result1) == 1
            assert test_url in result1
            assert result1[test_url]['valid'] is True
            assert call_count == 1, f"Expected 1 call to validate_url_format, got {call_count}"
            
            print(f"First call result: {result1[test_url]}")
            print(f"Call count after first call: {call_count}")
            
            # Now simulate time advancement by less than CACHE_TTL
            # We advance time by CACHE_TTL - 1 to ensure cache is still valid
            advanced_time = initial_time + CACHE_TTL - 1
            
            print(f"=== Advancing time by {CACHE_TTL - 1} seconds (cache should still be valid) ===")
            print(f"Original time: {initial_time}")
            print(f"Advanced time: {advanced_time}")
            
            # Patch time.time to return the advanced time (still within TTL)
            # We need to patch the time module as imported in url_utils
            with patch('src.utils.url_utils.time.time', return_value=advanced_time):
                print("=== Second call to validate_url_batch (cache should still be valid) ===")
                # Second call to validate_url_batch with the same URL list
                result2 = validate_url_batch(url_list, check_accessibility=False)
                
                # Verify second call returns identical result
                assert len(result2) == 1
                assert test_url in result2
                assert result2[test_url]['valid'] is True
                assert result2[test_url]['secure'] is True
                assert result2[test_url]['normalized'] is not None
                
                print(f"Second call result: {result2[test_url]}")
                print(f"Call count after second call: {call_count}")
                
                # KEY ASSERTION: validate_url_format should NOT have been called again
                # because the cache should still be valid
                assert call_count == 1, \
                    f"Expected validate_url_format to only be called once due to valid cache, " \
                    f"but it was called {call_count} times"
                
                # Verify the results are identical
                assert result1 == result2, "First and second call results should be identical"
                
                print("✓ Cache TTL not expired test passed!")


    def test_cache_ttl_expiry_focused(self):
        """
        Focused test that exactly matches Step 4 requirements:
        
        1. Patch validate_url_format to track calls while delegating to real implementation
        2. Call validate_url_batch([url]) once to populate cache
        3. Use patch('time.time', ...) to advance time by CACHE_TTL + 1
        4. Call validate_url_batch([url]) again
        5. Assert the patched validate_url_format *was* invoked the second time,
           demonstrating cache expiration via the public function
        """
        # Step 1: Patch validate_url_format
        test_url = "https://example.net"
        url_list = [test_url]
        
        original_validate_url_format = validate_url_format
        call_count = 0
        
        def track_validate_url_format(url):
            nonlocal call_count
            call_count += 1
            return original_validate_url_format(url)
        
        with patch('src.utils.url_utils.validate_url_format', 
                  side_effect=track_validate_url_format):
            
            # Step 2: Call validate_url_batch([url]) once to populate cache
            result1 = validate_url_batch(url_list, check_accessibility=False)
            assert result1[test_url]['valid'] is True
            assert call_count == 1  # validate_url_format was called once
            
            # Step 3: Use patch to advance time by CACHE_TTL + 1
            initial_time = time.time()
            advanced_time = initial_time + CACHE_TTL + 1
            
            with patch('src.utils.url_utils.time.time', return_value=advanced_time):
                
                # Step 4: Call validate_url_batch([url]) again
                result2 = validate_url_batch(url_list, check_accessibility=False)
                assert result2[test_url]['valid'] is True
                
                # Step 5: Assert the patched validate_url_format *was* invoked the second time
                assert call_count == 2, \
                    f"Cache should have expired! Expected validate_url_format to be called " \
                    f"twice (cache miss + cache expiry), but was called {call_count} times"
                
                print("✅ Step 4 requirements satisfied: Cache TTL expiry demonstrated!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
