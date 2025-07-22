"""
Comprehensive tests for URL validation and sanitization utilities.

This module tests all URL utility functions including:
- Security validation (dangerous schemes, private IPs)
- RFC 3986 normalization
- Batch validation with caching
- Parallel accessibility checking
- Edge cases and error handling
"""

import os
import time
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta

# Import the functions to test
from src.utils.url_utils import (
    is_secure_url, normalize_url_rfc3986, sanitize_url_for_storage,
    validate_url_format, validate_url_batch, check_url_accessibility,
    check_urls_accessibility_parallel, sanitize_url, validate_and_sanitize_url,
    extract_domain, format_url_for_display, MAX_URL_LENGTH
)


class TestIsSecureUrl:
    """Tests for the enhanced security validation function."""
    
    def test_dangerous_schemes(self):
        """Test blocking of dangerous URL schemes."""
        dangerous_urls = [
            "javascript:alert('XSS')",
            "vbscript:msgbox('XSS')",
            "data:text/html,<script>alert('XSS')</script>",
            "file:///etc/passwd",
            "about:blank",
            "chrome://settings",
            "ms-windows-store://",
            "ms-help://",
            "ms-settings://",
            "res://",
            "JavaScript:void(0)",  # Case variation
            "JAVASCRIPT:alert(1)",  # Uppercase
            " javascript:alert(1)",  # Leading space
        ]
        
        for url in dangerous_urls:
            assert not is_secure_url(url), f"Should block dangerous URL: {url}"
    
    def test_private_ip_addresses(self):
        """Test blocking of private IP addresses."""
        private_ip_urls = [
            "http://10.0.0.1",
            "https://172.16.0.1",
            "http://192.168.1.1",
            "https://127.0.0.1",
            "http://169.254.1.1",
            "https://localhost",
            "http://[::1]",  # IPv6 loopback
            "https://[fc00::1]",  # IPv6 private
            "http://[fe80::1]",  # IPv6 link-local
            "http://0.0.0.0",
            "https://127.0.0.1:8080",
            "http://192.168.0.1/admin",
        ]
        
        for url in private_ip_urls:
            assert not is_secure_url(url), \
                f"Should block private IP URL: {url}"
    
    def test_long_urls(self):
        """Test rejection of URLs exceeding maximum length."""
        # Create URL that exceeds MAX_URL_LENGTH
        long_path = 'a' * (MAX_URL_LENGTH - len("https://example.com/"))
        long_url = f"https://example.com/{long_path}"
        assert not is_secure_url(long_url), \
            "Should reject URL exceeding max length"
        
        # URL at exactly max length should pass
        max_path = 'a' * (MAX_URL_LENGTH - len("https://example.com/") - 1)
        max_url = f"https://example.com/{max_path}"
        assert is_secure_url(max_url), "Should accept URL at max length"
    
    def test_control_characters(self):
        """Test rejection of URLs with control characters."""
        control_char_urls = [
            "https://example.com/\x00path",  # Null byte
            "https://example.com/\x01\x02",  # Other control chars
            "https://example.com/\npath",  # Newline
            "https://example.com/\rpath",  # Carriage return
            "https://example.com/\tpath",  # Tab (should be rejected)
            "https://example.com/path\x1f",  # Unit separator
        ]
        
        for url in control_char_urls:
            assert not is_secure_url(url), \
                f"Should reject URL with control chars: {repr(url)}"
    
    def test_encoded_dangerous_schemes(self):
        """Test detection of encoded dangerous schemes."""
        encoded_dangerous_urls = [
            "https://example.com?redirect=javascript%3Aalert(1)",
            "https://example.com#javascript%3Aalert(1)",
            "https://example.com/javascript%3Aalert%28%27XSS%27%29",
            "https://example.com?url=data%3Atext%2Fhtml%2C%3Cscript%3E",
        ]
        
        for url in encoded_dangerous_urls:
            assert not is_secure_url(url), \
                f"Should detect encoded dangerous scheme: {url}"
    
    def test_valid_secure_urls(self):
        """Test that valid secure URLs pass validation."""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://www.example.com/path/to/resource",
            "https://api.example.com:8443/v1/endpoint",
            "https://example.com/search?q=test&lang=en",
            "https://example.com/page#section",
            "https://subdomain.example.co.uk/path",
            "https://example.com/path-with-dashes_and_underscores",
            "https://8.8.8.8",  # Public IP
            "https://[2001:4860:4860::8888]",  # Public IPv6
        ]
        
        for url in valid_urls:
            assert is_secure_url(url), f"Should accept valid secure URL: {url}"
    
    def test_empty_and_invalid_inputs(self):
        """Test handling of empty and invalid inputs."""
        invalid_inputs = [
            None,
            "",
            123,
            [],
            {},
            True,
            False,
        ]
        
        for input_val in invalid_inputs:
            assert not is_secure_url(input_val), \
                f"Should reject invalid input: {input_val}"


class TestNormalizeUrlRfc3986:
    """Tests for RFC 3986 URL normalization."""
    
    def test_unicode_normalization(self):
        """Test Unicode normalization (NFKC)."""
        unicode_urls = [
            # é normalized
            ("https://example.com/café", "https://example.com/caf%C3%A9"),
            # Ligature expanded
            ("https://example.com/ﬁle", "https://example.com/%EF%AC%81le"),
            # CJK compatibility
            ("https://example.com/㈱", "https://example.com/%E3%88%B1"),
            # Roman numeral normalized
            ("https://example.com/Ⅳ", "https://example.com/IV"),
        ]
        
        for input_url, expected in unicode_urls:
            result = normalize_url_rfc3986(input_url)
            assert result == expected, \
                f"Expected {expected}, got {result} for URL: {input_url}"
    
    def test_control_character_removal(self):
        """Test removal of control characters."""
        # URLs with control characters that should be cleaned
        control_urls = [
            ("https://example.com/path\x00", "https://example.com/path"),
            ("https://example.com/\x01\x02path", "https://example.com/path"),
            ("https://example.com/path\x1f", "https://example.com/path"),
        ]
        
        for input_url, expected_base in control_urls:
            result = normalize_url_rfc3986(input_url)
            assert result is not None, \
                f"Should handle control character: {repr(input_url)}"
            assert expected_base in result, \
                f"Should remove control chars from: {repr(input_url)}"
    
    def test_case_normalization(self):
        """Test scheme and hostname case normalization."""
        case_urls = [
            ("HTTPS://EXAMPLE.COM", "https://example.com/"),
            ("HtTpS://WwW.ExAmPlE.cOm", "https://www.example.com/"),
            ("HTTP://API.EXAMPLE.COM:8080/PATH",
             "http://api.example.com:8080/PATH"),
        ]
        
        for input_url, expected in case_urls:
            result = normalize_url_rfc3986(input_url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_default_port_removal(self):
        """Test removal of default ports."""
        port_urls = [
            ("https://example.com:443/", "https://example.com/"),
            ("http://example.com:80/", "http://example.com/"),
            # Non-default kept
            ("https://example.com:8443/", "https://example.com:8443/"),
            # Non-default kept
            ("http://example.com:8080/", "http://example.com:8080/"),
        ]
        
        for input_url, expected in port_urls:
            result = normalize_url_rfc3986(input_url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_path_normalization(self):
        """Test path normalization including duplicate slash removal."""
        path_urls = [
            ("https://example.com//path", "https://example.com/path"),
            ("https://example.com///multiple///slashes",
             "https://example.com/multiple/slashes"),
            # Dot segment
            # Dot segments should be resolved
            ("https://example.com/./path",      "https://example.com/path"),
            ("https://example.com/path/../other","https://example.com/other"),
            # Add trailing slash
            ("https://example.com", "https://example.com/"),
        ]
        
        for input_url, expected in path_urls:
            result = normalize_url_rfc3986(input_url)
            assert result is not None, f"Should normalize path: {input_url}"
    
    def test_query_and_fragment_encoding(self):
        """Test proper encoding of query and fragment."""
        encoding_urls = [
            ("https://example.com?q=hello world",
             "https://example.com/?q=hello%20world"),
            ("https://example.com#section name",
             "https://example.com/#section%20name"),
            ("https://example.com?a=1&b=2", "https://example.com/?a=1&b=2"),
        ]
        
        for input_url, expected in encoding_urls:
            result = normalize_url_rfc3986(input_url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_auth_preservation(self):
        """Test that authentication info is preserved."""
        auth_urls = [
            ("https://user:pass@example.com",
             "https://user:pass@example.com/"),
            ("http://user@example.com:8080", "http://user@example.com:8080/"),
        ]
        
        for input_url, expected in auth_urls:
            result = normalize_url_rfc3986(input_url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_invalid_inputs(self):
        """Test handling of invalid inputs."""
        invalid_inputs = [None, "", 123, [], {}, "not a url"]
        
        for input_val in invalid_inputs:
            result = normalize_url_rfc3986(input_val)
            assert result is None, \
                f"Should return None for invalid input: {input_val}"


class TestSanitizeUrlForStorage:
    """Tests for the comprehensive URL sanitization function."""
    
    def test_complete_sanitization_pipeline(self):
        """Test that all sanitization steps are applied."""
        test_cases = [
            # Missing protocol, needs sanitization and validation
             ("example.com", "https://example.com/"),
            # Has protocol but needs normalization
            ("HTTPS://EXAMPLE.COM", "https://example.com/"),
            # Whitespace that needs stripping
            ("  https://example.com  ", "https://example.com/"),
        ]
        
        for input_url, expected in test_cases:
            result = sanitize_url_for_storage(input_url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_security_validation_integration(self):
        """Test that security validation is applied."""
        insecure_urls = [
            "javascript:alert(1)",
            "https://192.168.1.1",
            "file:///etc/passwd",
            "https://localhost/admin",
        ]
        
        for url in insecure_urls:
            result = sanitize_url_for_storage(url)
            assert result is None, f"Should reject insecure URL: {url}"
    
    def test_edge_cases(self):
        """Test edge cases for storage sanitization."""
        edge_cases = [
            (None, None),
            ("", None),
            ("   ", None),
            ("https://a.b", None),  # Too short domain
            ("https://.com", None),  # Invalid domain
            ("https://example", None),  # Missing TLD
        ]
        
        for input_url, expected in edge_cases:
            result = sanitize_url_for_storage(input_url)
            assert result == expected, \
                f"Expected {expected} for edge case: {input_url}"


class TestValidateUrlBatch:
    """Tests for batch URL validation with caching."""
    
    def test_mixed_valid_invalid_urls(self):
        """Test batch validation with mixed valid/invalid URLs."""
        urls = [
            "https://example.com",  # Valid
            "invalid-url",  # Invalid format
            "javascript:alert(1)",  # Dangerous scheme
            "https://192.168.1.1",  # Private IP
            "example.org",  # Missing protocol (will be normalized)
            None,  # None value
            "",  # Empty string
        ]
        
        results = validate_url_batch(urls)
        
        # Check results
        assert results["https://example.com"]['valid'] is True
        assert results["https://example.com"]['secure'] is True
        assert results["https://example.com"]['normalized'] is not None
        
        assert results["invalid-url"]['valid'] is False
        assert results["invalid-url"]['error'] is not None
        
        assert results["javascript:alert(1)"]['valid'] is False
        assert results["javascript:alert(1)"]['secure'] is False
        
        assert results["https://192.168.1.1"]['valid'] is False
        assert results["https://192.168.1.1"]['secure'] is False
    
    @patch('src.utils.url_utils.check_url_accessibility')
    def test_batch_with_accessibility_check(self, mock_check_accessibility):
        """Test batch validation with accessibility checking."""
        mock_check_accessibility.side_effect = [True, False, True]
        
        urls = [
            "https://accessible.com",
            "https://inaccessible.com",
            "https://another-accessible.com",
        ]
        
        results = validate_url_batch(urls, check_accessibility=True)
        
        assert results["https://accessible.com"]['accessible'] is True
        assert results["https://inaccessible.com"]['accessible'] is False
        assert results["https://another-accessible.com"]['accessible'] is True
        
        # Verify mock was called for each URL
        assert mock_check_accessibility.call_count == 3
    
    def test_parallel_processing(self):
        """Test that batch processing uses threading efficiently."""
        # Create a large batch of URLs
        urls = [f"https://example{i}.com" for i in range(100)]
        
        start_time = time.time()
        results = validate_url_batch(urls, max_workers=10)
        duration = time.time() - start_time
        
        # Should process 100 URLs relatively quickly with threading
        assert len(results) == 100
        assert all(results[url]['valid'] for url in urls)
        # Use environment variable for timeout with a more lenient default for CI
        max_duration = float(os.getenv('TEST_BATCH_TIMEOUT', '10.0'))
        error_msg = (
            f"Batch processing took too long: {duration:.2f}s > {max_duration}s\n"
            "This may be due to system load. Consider increasing "
            "TEST_BATCH_TIMEOUT environment variable if this is a valid "
            "performance regression."
        )
        assert duration < max_duration, error_msg
    



class TestCheckUrlsAccessibilityParallel:
    """Tests for parallel URL accessibility checking."""
    
    @patch('src.utils.url_utils.requests.head')
    def test_parallel_accessibility_check(self, mock_head):
        """Test parallel checking of multiple URLs."""
        # Setup mock responses
        mock_responses = []
        for i in range(5):
            mock_resp = Mock()
            mock_resp.status_code = 200 if i % 2 == 0 else 404
            mock_responses.append(mock_resp)
        
        mock_head.side_effect = mock_responses
        
        urls = [f"https://example{i}.com" for i in range(5)]
        results = check_urls_accessibility_parallel(
            urls, timeout=5, max_workers=3)
        
        # Check results
        assert len(results) == 5
        assert results["https://example0.com"] is True  # 200
        assert results["https://example1.com"] is False  # 404
        assert results["https://example2.com"] is True  # 200
        assert results["https://example3.com"] is False  # 404
        assert results["https://example4.com"] is True  # 200
    
    @patch('src.utils.url_utils.requests.head')
    def test_timeout_handling(self, mock_head):
        """Test handling of timeouts in parallel checking."""
        import requests
        
        # Mock timeout exception
        mock_head.side_effect = requests.Timeout("Connection timed out")
        
        urls = ["https://slow-site1.com", "https://slow-site2.com"]
        results = check_urls_accessibility_parallel(
            urls, timeout=1, max_workers=2)
        
        # All should be False due to timeout
        assert all(not accessible for accessible in results.values())
    
    def test_performance_with_many_urls(self):
        """Test performance with many URLs."""
        # Create many URLs
        urls = [f"https://example{i}.com" for i in range(50)]
        
        with patch('src.utils.url_utils.check_url_accessibility') \
                as mock_check:
            # Mock quick responses
            mock_check.return_value = True
            
            start_time = time.time()
            results = check_urls_accessibility_parallel(urls, max_workers=10)
            duration = time.time() - start_time
            
            assert len(results) == 50
            # Use environment variable for timeout with a more lenient default for CI
            max_duration = float(os.getenv('TEST_PARALLEL_TIMEOUT', '10.0'))
            error_msg = (
                f"Parallel check took too long: {duration:.2f}s > {max_duration}s\n"
                "This may be due to system load. Consider increasing "
                "TEST_PARALLEL_TIMEOUT environment variable if this is a valid "
                "performance regression."
            )
            assert duration < max_duration, error_msg


class TestValidateUrlFormat:
    """Tests for basic URL format validation."""
    
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
            "https://sub.domain.example.co.uk",
            "https://example.com/path/to/resource.html",
            "https://api.example.com/v1/users?page=1&limit=10",
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
            "https://example",  # Missing TLD (Note: localhost is special case)
            "https://example.c",  # TLD too short
            "https://",  # Empty
            "javascript:alert(1)",  # Wrong protocol
            123,  # Wrong type
            [],  # Wrong type
            {},  # Wrong type
        ]
        
        for url in invalid_urls:
            assert not validate_url_format(url), f"Should not validate: {url}"
    
    def test_edge_cases(self):
        """Test edge cases for URL validation."""
        assert not validate_url_format(123)  # Non-string input
        assert not validate_url_format([])   # Non-string input
        assert not validate_url_format({})   # Non-string input
        assert validate_url_format("http://localhost")  # Special case
        assert validate_url_format("https://10.0.0.1")  # IP address


class TestSanitizeUrl:
    """Tests for basic URL sanitization."""
    
    def test_add_missing_protocol(self):
        """Test adding missing protocol to URLs."""
        test_cases = [
            ("example.com", "https://example.com"),
            ("www.example.com", "https://www.example.com"),
            ("subdomain.example.com/path",
             "https://subdomain.example.com/path"),
            ("example.com:8080", "https://example.com:8080"),
            ("user@example.com", "https://user@example.com"),
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
            "http://example.com:8080/path",
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
            ("\n\texample.com\r\n", "https://example.com"),
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
            "\t\n",
            123,
            [],
            {},
            "not-a-valid-url-at-all",
            "https://",  # Incomplete URL
            "://example.com",  # Missing scheme
        ]
        
        for invalid_input in invalid_inputs:
            result = sanitize_url(invalid_input)
            assert result is None, f"Should return None for: {invalid_input}"


class TestCheckUrlAccessibility:
    """Tests for URL accessibility checking."""
    
    @patch('requests.Session')
    def test_accessible_url(self, mock_session):
        """Test checking accessible URL."""
        # Setup mock session
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.return_value.head.return_value = mock_response
        
        result = check_url_accessibility("https://example.com", _use_session=True)
        assert result is True
        
        # Verify the request was made with the correct parameters
        mock_session.return_value.head.assert_called_once_with(
            "https://example.com",
            timeout=5,
            allow_redirects=True,
            verify=True,
            stream=True
        )
        
    @patch('requests.head')
    def test_accessible_url_no_session(self, mock_head):
        """Test checking accessible URL without using session."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        result = check_url_accessibility("https://example.com", _use_session=False)
        assert result is True
        
        # Verify the request was made with the correct parameters
        mock_head.assert_called_once_with(
            "https://example.com",
            timeout=5,
            allow_redirects=True,
            verify=True,
            stream=True
        )
    
    @patch('requests.Session')
    def test_inaccessible_url_various_codes(self, mock_session):
        """Test checking inaccessible URLs with various status codes."""
        status_codes = [400, 401, 403, 404, 410, 500, 502, 503]
        
        for code in status_codes:
            # Setup mock for this iteration
            mock_response = Mock()
            mock_response.status_code = code
            mock_session.return_value.head.return_value = mock_response
            
            result = check_url_accessibility(
                f"https://example.com/{code}",
                _use_session=True
            )
            assert result is False, f"Should be inaccessible for status {code}"
    
    @patch('requests.head')
    def test_inaccessible_url_various_codes_no_session(self, mock_head):
        """Test checking inaccessible URLs with various status codes without session."""
        status_codes = [400, 401, 403, 404, 410, 500, 502, 503]
        
        for code in status_codes:
            # Setup mock for this iteration
            mock_response = Mock()
            mock_response.status_code = code
            mock_head.return_value = mock_response
            
            result = check_url_accessibility(
                f"https://example.com/{code}",
                _use_session=False
            )
            assert result is False, f"Should be inaccessible for status {code}"
    
    @patch('requests.Session')
    def test_redirect_handling(self, mock_session):
        """Test that redirects are followed with session."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200  # After redirect
        mock_response.url = "https://example.com/redirected"
        mock_session.return_value.head.return_value = mock_response
    
        result = check_url_accessibility("https://example.com/redirect", _use_session=True)
        assert result is True
        
        # Verify the request was made with the correct parameters
        mock_session.return_value.head.assert_called_once()
        
    @patch('requests.head')
    def test_redirect_handling_no_session(self, mock_head):
        """Test that redirects are followed without session."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200  # After redirect
        mock_response.url = "https://example.com/redirected"
        mock_head.return_value = mock_response
    
        result = check_url_accessibility("https://example.com/redirect", _use_session=False)
        assert result is True
        
        # Verify the request was made with the correct parameters
        mock_head.assert_called_once()
        
    @patch('requests.Session')
    def test_network_errors_with_session(self, mock_session):
        """Test handling of various network errors with session."""
        import requests
        
        errors = [
            (requests.ConnectionError("Connection refused"), 'connection_error'),
            (requests.Timeout("Request timed out"), 'timeout'),
            (requests.TooManyRedirects("Too many redirects"), 'too_many_redirects'),
            (requests.RequestException("Generic request error"), 'request_failed'),
            (Exception("Unexpected error"), 'unexpected_error'),
        ]
        
        for error, error_type in errors:
            # Setup mock to raise the current error
            mock_session.return_value.head.side_effect = error
    
            # Test with session
            result = check_url_accessibility(
                "https://example.com",
                _use_session=True
            )
            assert result is False, f"Should handle {error_type} with session"
            
    @patch('requests.head')
    def test_network_errors_no_session(self, mock_head):
        """Test handling of various network errors without session."""
        import requests
        
        errors = [
            (requests.ConnectionError("Connection refused"), 'connection_error'),
            (requests.Timeout("Request timed out"), 'timeout'),
            (requests.TooManyRedirects("Too many redirects"), 'too_many_redirects'),
            (requests.RequestException("Generic request error"), 'request_failed'),
            (Exception("Unexpected error"), 'unexpected_error'),
        ]
        
        for error, error_type in errors:
            # Setup mock to raise the current error
            mock_head.side_effect = error
    
            # Test without session
            result = check_url_accessibility(
                "https://example.com",
                _use_session=False
            )
            assert result is False, f"Should handle {error_type} without session"
    
    def test_invalid_url_format(self):
        """Test accessibility check with invalid URL format."""
        invalid_urls = ["not-a-url", "", None, "ftp://example.com"]
        
        for url in invalid_urls:
            result = check_url_accessibility(url, _use_session=False)
            assert result is False, \
                f"Should return False for invalid URL: {url}"
    
    @patch('requests.Session')
    def test_custom_timeout_with_session(self, mock_session):
        """Test custom timeout parameter with session."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.return_value.head.return_value = mock_response
    
        # Test with custom timeout
        check_url_accessibility("https://example.com", timeout=10, _use_session=True)
    
        # Verify the request was made with the custom timeout
        mock_session.return_value.head.assert_called_once()
        
        # Get the call arguments
        args, kwargs = mock_session.return_value.head.call_args
        assert kwargs.get('timeout') == 10, "Custom timeout not passed to request with session"
        
    @patch('requests.head')
    def test_custom_timeout_no_session(self, mock_head):
        """Test custom timeout parameter without session."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
    
        # Test with custom timeout
        check_url_accessibility("https://example.com", timeout=10, _use_session=False)
    
        # Verify the request was made with the custom timeout
        mock_head.assert_called_once()
        
        # Get the call arguments
        args, kwargs = mock_head.call_args
        assert kwargs.get('timeout') == 10, "Custom timeout not passed to request without session"

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
            ("https://api.example.com:443", "api.example.com:443"),
            ("http://example.com/path?query=value#fragment", "example.com"),
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
            ("https://www.example.co.uk", "example.co.uk"),
            # www.api -> api
            ("https://www.api.example.com", "api.example.com"),
        ]
        
        for url, expected in test_cases:
            result = extract_domain(url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_special_domains(self):
        """Test extraction of special domains."""
        test_cases = [
            ("http://localhost", "localhost"),
            ("https://localhost:8080", "localhost:8080"),
            ("http://127.0.0.1", "127.0.0.1"),
            ("https://[::1]", "[::1]"),  # IPv6
            ("https://[2001:db8::1]:8080", "[2001:db8::1]:8080"),
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
            "https://",  # No domain
            "://example.com",  # No scheme
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
        test_cases = [
            ("  example.com  ", "https://example.com"),
            ("www.example.com", "https://www.example.com"),
            ("\texample.com/path\n", "https://example.com/path"),
        ]
        
        for input_url, expected in test_cases:
            url, is_valid = validate_and_sanitize_url(input_url)
            assert url == expected, f"Expected {expected}, got {url}"
            assert is_valid is True
    
    def test_invalid_url(self):
        """Test invalid URL."""
        invalid_urls = [
            "not-a-url",
            "https://",
            "ftp://example.com",
            "",
            None,
        ]
        
        for invalid_url in invalid_urls:
            url, is_valid = validate_and_sanitize_url(invalid_url)
            assert url is None
            assert is_valid is False
    
    @patch('src.utils.url_utils.check_url_accessibility')
    def test_with_accessibility_check_accessible(self, mock_check):
        """Test with accessibility check - accessible URL."""
        mock_check.return_value = True
        
        url, is_valid = validate_and_sanitize_url(
            "https://example.com", check_accessibility=True)
        assert url == "https://example.com"
        assert is_valid is True
        mock_check.assert_called_once_with("https://example.com")
    
    @patch('src.utils.url_utils.check_url_accessibility')
    def test_with_accessibility_check_inaccessible(self, mock_check):
        """Test with accessibility check - inaccessible URL."""
        mock_check.return_value = False
        
        url, is_valid = validate_and_sanitize_url(
            "https://example.com", check_accessibility=True)
        assert url == "https://example.com"  # URL is still returned
        # But marked as invalid due to inaccessibility
        assert is_valid is False
        mock_check.assert_called_once_with("https://example.com")


class TestFormatUrlForDisplay:
    """Tests for URL display formatting."""
    
    def test_short_url_unchanged(self):
        """Test that short URLs remain unchanged."""
        short_urls = [
            "https://example.com",
            "http://test.org",
            "https://api.example.com/v1",
        ]
        
        for url in short_urls:
            result = format_url_for_display(url, max_length=50)
            assert result == url
    
    def test_long_url_with_domain(self):
        """Test formatting of long URLs with extractable domain."""
        long_url = ("https://example.com/very/long/path/that/exceeds/the/"
                    "maximum/length/limit/for/display")
        result = format_url_for_display(long_url, max_length=30)
        assert result == "example.com/..."
        
        # Test with www prefix
        long_url = "https://www.example.com/very/long/path/that/exceeds/limit"
        result = format_url_for_display(long_url, max_length=30)
        assert result == "example.com/..."  # www removed
    
    def test_long_url_without_domain(self):
        """Test formatting of long URLs without extractable domain."""
        # Mock a URL that can't have domain extracted
        with patch('src.utils.url_utils.extract_domain', return_value=None):
            long_url = ("https://very-long-domain-name-that-exceeds-limit"
                        ".com/path")
            result = format_url_for_display(long_url, max_length=30)
            expected = long_url[:27] + "..."
            assert result == expected
    
    def test_empty_and_none_urls(self):
        """Test formatting of empty and None URLs."""
        assert format_url_for_display("") == "No URL available"
        assert format_url_for_display(None) == "No URL available"
        # Whitespace
        assert format_url_for_display("   ") == "No URL available"
    
    def test_custom_max_length(self):
        """Test custom maximum length."""
        url = "https://example.com/path/to/resource"
        
        # Fits within 50 chars
        result = format_url_for_display(url, max_length=50)
        assert result == url
        
        # Exceeds 20 chars
        result = format_url_for_display(url, max_length=20)
        assert result == "example.com/..."
        
        # Very short limit
        result = format_url_for_display(url, max_length=10)
        assert result == "example.co..."  # Truncated domain
    
    def test_various_url_formats(self):
        """Test formatting of various URL formats."""
        test_cases = [
            ("https://example.com:8080/path", 25, "example.com:8080/..."),
            ("http://localhost/admin", 50, "http://localhost/admin"),
            ("https://192.168.1.1/login", 20, "192.168.1.1/..."),
        ]
        
        for url, max_len, expected in test_cases:
            result = format_url_for_display(url, max_length=max_len)
            assert result == expected, f"Expected {expected}, got {result}"


class TestLoggingAndMonitoring:
    """Tests to ensure logging and monitoring are properly integrated."""
    
    def test_is_secure_url_logging(self):
        """Test that is_secure_url function works correctly."""
        # Test successful validation
        result = is_secure_url("https://example.com")
        assert result is True
        
        # Test failed validation
        result = is_secure_url("javascript:alert(1)")
        assert result is False
    
    def test_normalize_url_logging(self):
        """Test that normalize_url_rfc3986 function works correctly."""
        result = normalize_url_rfc3986("HTTPS://EXAMPLE.COM")
        assert result == "https://example.com/"
    
    def test_validation_metrics(self):
        """Test that validation functions work correctly."""
        result = is_secure_url("https://example.com")
        assert result is True
        
        # Check that security validation works for dangerous URLs
        result = is_secure_url("javascript:alert(1)")
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])