"""
Step 3: Add public-API test: basic cache hit

This test verifies that validate_url_batch properly caches results by patching 
validate_url_format so that it still delegates to the real implementation but 
records call count. The test ensures the cache works without touching private helpers.

Requirements:
1. Patch src.utils.url_utils.validate_url_format so it delegates to real implementation 
   but records call count  
2. Call validate_url_batch([url]) twice with same URL list and check_accessibility=False  
3. Assert:  
   • First call returns valid result  
   • Second call returns identical result AND the patched validate_url_format was 
     NOT invoked again, showing the cache was used  
   (No private helpers touched)
"""

import pytest
from unittest.mock import patch
from src.utils.url_utils import validate_url_batch, validate_url_format


class TestPublicAPICacheHit:
    """Test for basic cache hit functionality using only public API."""
    
    def test_basic_cache_hit(self):
        """
        Test that validate_url_batch properly caches results on repeated calls.
        
        This test:
        1. Patches validate_url_format to track calls while delegating to real implementation
        2. Calls validate_url_batch twice with the same URL and check_accessibility=False
        3. Verifies that:
           - First call returns valid result
           - Second call returns identical result
           - validate_url_format was NOT called again on second call (cache hit)
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
            return original_validate_url_format(url)
        
        # Patch validate_url_format to track calls
        with patch('src.utils.url_utils.validate_url_format', 
                  side_effect=mock_validate_url_format) as mock_func:
            
            # First call to validate_url_batch
            result1 = validate_url_batch(url_list, check_accessibility=False)
            
            # Verify first call returns valid result and called validate_url_format
            assert len(result1) == 1
            assert test_url in result1
            assert result1[test_url]['valid'] is True
            assert result1[test_url]['secure'] is True
            assert result1[test_url]['normalized'] is not None
            assert result1[test_url]['error'] is None
            assert call_count == 1, f"Expected 1 call to validate_url_format, got {call_count}"
            
            # Second call to validate_url_batch with same URL list
            result2 = validate_url_batch(url_list, check_accessibility=False)
            
            # Verify second call returns identical result
            assert len(result2) == 1
            assert test_url in result2
            assert result2[test_url]['valid'] is True
            assert result2[test_url]['secure'] is True
            assert result2[test_url]['normalized'] is not None
            assert result2[test_url]['error'] is None
            
            # KEY ASSERTION: validate_url_format should NOT have been called again
            # because the cache should have been used
            assert call_count == 1, \
                f"Expected validate_url_format to only be called once due to caching, " \
                f"but it was called {call_count} times"
            
            # Verify the results are identical
            assert result1 == result2, "First and second call results should be identical"
    


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
