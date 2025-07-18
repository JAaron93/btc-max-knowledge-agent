"""
Comprehensive tests for URL validation and sanitization utilities.
"""

import pytest
from unittest.mock import patch, Mock
from src.utils.url_utils import (
    validate_url_format,
    sanitize_url,
    check_url_accessibility,
    extract_domain,
    validate_and_sanitize_url,
    format_url_for_display
)


class TestValidateUrlFormat:
    """Tests for URL format validation."""
    
    def test_valid_http_urls(self):
        """Test validation of valid HTTP URLs."""
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "https://www.example.com",
            "https://subdomain.example.com",
            "https://example.com/path",
            "https://example.com/path?query=value",
            "https://example.com:8080",
            "http://localhost:3000",
            "https://192.168.1.1",
        ]
        
        for url in valid_urls:
            assert validate_url_format(url), f"Should validate: {url}"
    
    def test_invalid_urls(self):
        """Test validation of invalid URLs."""
        invalid_urls = [
            "",
            None,
            "not-a-url",
            "ftp://example.com",  # Only HTTP/HTTPS supported
            "example.com",  # Missing protocol
            "https://",  # Missing domain
            "https://.com",  # Invalid domain
            "https://example",  # Missing TLD
        ]
        
        for url in invalid_urls:
            assert not validate_url_format(url), f"Should not validate: {url}"
    
    def test_edge_cases(self):
        """Test edge cases for URL validation."""
        assert not validate_url_format(123)  # Non-string input
        assert not validate_url_format([])   # Non-string input
        assert not validate_url_format({})   # Non-string input


class TestSanitizeUrl:
    """Tests for URL sanitization."""
    
    def test_add_missing_protocol(self):
        """Test adding missing protocol to URLs."""
        test_cases = [
            ("example.com", "https://example.com"),
            ("www.example.com", "https://www.example.com"),
            ("subdomain.example.com/path", "https://subdomain.example.com/path"),
        ]
        
        for input_url, expected in test_cases:
            result = sanitize_url(input_url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_preserve_existing_protocol(self):
        """Test that existing protocols are preserved."""
        test_cases = [
            "http://example.com",
            "https://example.com",
            "https://www.example.com/path?query=value",
        ]
        
        for url in test_cases:
            result = sanitize_url(url)
            assert result == url, f"Should preserve: {url}"
    
    def test_strip_whitespace(self):
        """Test whitespace stripping."""
        test_cases = [
            ("  https://example.com  ", "https://example.com"),
            ("\thttps://example.com\n", "https://example.com"),
            ("  example.com  ", "https://example.com"),
        ]
        
        for input_url, expected in test_cases:
            result = sanitize_url(input_url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_invalid_inputs(self):
        """Test handling of invalid inputs."""
        invalid_inputs = [
            None,
            "",
            "   ",
            123,
            [],
            {},
            "not-a-valid-url-at-all",
        ]
        
        for invalid_input in invalid_inputs:
            result = sanitize_url(invalid_input)
            assert result is None, f"Should return None for: {invalid_input}"


class TestCheckUrlAccessibility:
    """Tests for URL accessibility checking."""
    
    @patch('src.utils.url_utils.requests.head')
    def test_accessible_url(self, mock_head):
        """Test checking accessible URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        result = check_url_accessibility("https://example.com")
        assert result is True
        mock_head.assert_called_once_with("https://example.com", timeout=5, allow_redirects=True)
    
    @patch('src.utils.url_utils.requests.head')
    def test_inaccessible_url_404(self, mock_head):
        """Test checking inaccessible URL (404)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response
        
        result = check_url_accessibility("https://example.com/nonexistent")
        assert result is False
    
    @patch('src.utils.url_utils.requests.head')
    def test_inaccessible_url_500(self, mock_head):
        """Test checking inaccessible URL (500)."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_head.return_value = mock_response
        
        result = check_url_accessibility("https://example.com/error")
        assert result is False
    
    @patch('src.utils.url_utils.requests.head')
    def test_network_error(self, mock_head):
        """Test handling network errors."""
        mock_head.side_effect = Exception("Network error")
        
        result = check_url_accessibility("https://example.com")
        assert result is False
    
    def test_invalid_url_format(self):
        """Test accessibility check with invalid URL format."""
        result = check_url_accessibility("not-a-url")
        assert result is False
    
    @patch('src.utils.url_utils.requests.head')
    def test_custom_timeout(self, mock_head):
        """Test custom timeout parameter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        check_url_accessibility("https://example.com", timeout=10)
        mock_head.assert_called_once_with("https://example.com", timeout=10, allow_redirects=True)


class TestExtractDomain:
    """Tests for domain extraction."""
    
    def test_extract_basic_domain(self):
        """Test extracting basic domain names."""
        test_cases = [
            ("https://example.com", "example.com"),
            ("http://example.com", "example.com"),
            ("https://subdomain.example.com", "subdomain.example.com"),
            ("https://example.com/path", "example.com"),
            ("https://example.com:8080", "example.com:8080"),
        ]
        
        for url, expected in test_cases:
            result = extract_domain(url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_remove_www_prefix(self):
        """Test removal of www prefix."""
        test_cases = [
            ("https://www.example.com", "example.com"),
            ("http://www.subdomain.example.com", "subdomain.example.com"),
            ("https://www.example.com/path", "example.com"),
        ]
        
        for url, expected in test_cases:
            result = extract_domain(url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_invalid_inputs(self):
        """Test handling of invalid inputs."""
        invalid_inputs = [
            None,
            "",
            123,
            [],
            {},
            "not-a-url",
        ]
        
        for invalid_input in invalid_inputs:
            result = extract_domain(invalid_input)
            assert result is None, f"Should return None for: {invalid_input}"


class TestValidateAndSanitizeUrl:
    """Tests for comprehensive URL validation and sanitization."""
    
    def test_valid_url_without_accessibility_check(self):
        """Test valid URL without accessibility check."""
        url, is_valid = validate_and_sanitize_url("https://example.com")
        assert url == "https://example.com"
        assert is_valid is True
    
    def test_url_needing_sanitization(self):
        """Test URL that needs sanitization."""
        url, is_valid = validate_and_sanitize_url("  example.com  ")
        assert url == "https://example.com"
        assert is_valid is True
    
    def test_invalid_url(self):
        """Test invalid URL."""
        url, is_valid = validate_and_sanitize_url("not-a-url")
        assert url is None
        assert is_valid is False
    
    def test_empty_url(self):
        """Test empty URL."""
        url, is_valid = validate_and_sanitize_url("")
        assert url is None
        assert is_valid is False
    
    @patch('src.utils.url_utils.check_url_accessibility')
    def test_with_accessibility_check_accessible(self, mock_check):
        """Test with accessibility check - accessible URL."""
        mock_check.return_value = True
        
        url, is_valid = validate_and_sanitize_url("https://example.com", check_accessibility=True)
        assert url == "https://example.com"
        assert is_valid is True
        mock_check.assert_called_once_with("https://example.com")
    
    @patch('src.utils.url_utils.check_url_accessibility')
    def test_with_accessibility_check_inaccessible(self, mock_check):
        """Test with accessibility check - inaccessible URL."""
        mock_check.return_value = False
        
        url, is_valid = validate_and_sanitize_url("https://example.com", check_accessibility=True)
        assert url == "https://example.com"
        assert is_valid is False
        mock_check.assert_called_once_with("https://example.com")


class TestFormatUrlForDisplay:
    """Tests for URL display formatting."""
    
    def test_short_url_unchanged(self):
        """Test that short URLs remain unchanged."""
        url = "https://example.com"
        result = format_url_for_display(url)
        assert result == url
    
    def test_long_url_with_domain(self):
        """Test formatting of long URLs with extractable domain."""
        long_url = "https://example.com/very/long/path/that/exceeds/the/maximum/length/limit"
        result = format_url_for_display(long_url, max_length=30)
        assert result == "example.com/..."
    
    def test_long_url_without_domain(self):
        """Test formatting of long URLs without extractable domain."""
        # Mock a URL that can't have domain extracted
        with patch('src.utils.url_utils.extract_domain', return_value=None):
            long_url = "https://very-long-domain-name-that-exceeds-limit.com"
            result = format_url_for_display(long_url, max_length=30)
            expected = long_url[:27] + "..."
            assert result == expected
    
    def test_empty_url(self):
        """Test formatting of empty URL."""
        result = format_url_for_display("")
        assert result == "No URL available"
    
    def test_none_url(self):
        """Test formatting of None URL."""
        result = format_url_for_display(None)
        assert result == "No URL available"
    
    def test_custom_max_length(self):
        """Test custom maximum length."""
        url = "https://example.com/path"
        result = format_url_for_display(url, max_length=30)
        assert result == url  # Still fits within limit
        
        result = format_url_for_display(url, max_length=15)
        assert result == "example.com/..."  # Exceeds limit


if __name__ == "__main__":
    pytest.main([__file__])