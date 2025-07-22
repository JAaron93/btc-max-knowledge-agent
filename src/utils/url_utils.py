"""
URL validation and sanitization utilities for the Bitcoin knowledge agent.

This module provides functions to validate, sanitize, and process URLs
for use in the Pinecone vector database metadata.

Enhanced with RFC 3986 compliance and security-focused validation to prevent
injection attacks and ensure safe URL storage.
"""

import re
from typing import Optional, Tuple, List, Dict
import requests
from urllib.parse import urlparse, urlunparse, quote, unquote
import unicodedata
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from threading import Lock

# Import logging infrastructure
from src.utils.url_metadata_logger import (
    log_validation, log_sanitization, correlation_context
)
from src.monitoring.url_metadata_monitor import (
    record_validation, check_url_accessibility as monitor_url_check
)


# Security constants
DANGEROUS_SCHEMES = {
    'javascript', 'vbscript', 'data', 'file', 'about', 'chrome',
    'ms-windows-store', 'ms-help', 'ms-settings', 'res'
}
ALLOWED_SCHEMES = {'http', 'https'}
MAX_URL_LENGTH = 2048
PRIVATE_IP_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10')
]

# Cache for URL validation results
_validation_cache: Dict[str, Tuple[bool, float]] = {}
_cache_lock = Lock()
CACHE_TTL = 3600  # 1 hour in seconds


def is_secure_url(url: str) -> bool:
    """
    Comprehensive security validation for URLs to prevent injection attacks.
    
    This function performs multiple security checks:
    - Blocks dangerous URL schemes (javascript:, file://, data:, etc.)
    - Validates against private IP addresses
    - Enforces maximum URL length
    - Only allows http:// and https:// protocols
    - Removes control characters and validates encoding
    
    Args:
        url: The URL string to validate
        
    Returns:
        bool: True if URL passes all security checks, False otherwise
    """
    start_time = time.time()
    validation_details = {}
    
    if not url or not isinstance(url, str):
        log_validation(url or '', False, 'security_check',
                      details={'error': 'empty_or_invalid_type'})
        return False
    
    # Check URL length
    if len(url) > MAX_URL_LENGTH:
        validation_details['error'] = f'url_too_long: {len(url)} chars'
        log_validation(url, False, 'security_check', details=validation_details)
        return False
    
    # Remove control characters
    url_clean = ''.join(char for char in url if ord(char) >= 32)
    if url_clean != url:
        validation_details['error'] = 'contains_control_characters'
        log_validation(url, False, 'security_check', details=validation_details)
        return False
    
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if not parsed.scheme or parsed.scheme.lower() not in ALLOWED_SCHEMES:
            validation_details['error'] = f'invalid_scheme: {parsed.scheme}'
            log_validation(url, False, 'security_check', details=validation_details)
            return False
        
        # Check for dangerous schemes (double-check)
        if parsed.scheme.lower() in DANGEROUS_SCHEMES:
            validation_details['error'] = f'dangerous_scheme: {parsed.scheme}'
            log_validation(url, False, 'security_check', details=validation_details)
            return False
        
        # Check hostname
        if not parsed.hostname:
            validation_details['error'] = 'missing_hostname'
            log_validation(url, False, 'security_check', details=validation_details)
            return False
        
        # Check for private IP addresses
        try:
            # Try to parse as IP address
            ip = ipaddress.ip_address(parsed.hostname)
            for private_range in PRIVATE_IP_RANGES:
                if ip in private_range:
                    validation_details['error'] = f'private_ip: {ip}'
                    log_validation(url, False, 'security_check',
                                 details=validation_details)
                    return False
        except ValueError:
            # Not an IP address, check for localhost
            if parsed.hostname.lower() in ['localhost', '127.0.0.1', '::1']:
                validation_details['error'] = 'localhost_not_allowed'
                log_validation(url, False, 'security_check',
                             details=validation_details)
                return False
        
        # Check for null bytes
        if '\x00' in url:
            validation_details['error'] = 'contains_null_bytes'
            log_validation(url, False, 'security_check', details=validation_details)
            return False
        
        # Additional checks for encoded dangerous characters
        decoded_url = unquote(url)
        dangerous_found = False
        for scheme in DANGEROUS_SCHEMES:
            if scheme + ':' in decoded_url.lower():
                dangerous_found = True
                validation_details['error'] = f'encoded_dangerous_scheme: {scheme}'
                break
        if dangerous_found:
            log_validation(url, False, 'security_check', details=validation_details)
            return False
        
        # Success - log and record metrics
        duration_ms = (time.time() - start_time) * 1000
        log_validation(url, True, 'security_check', duration_ms=duration_ms)
        record_validation(url, True, duration_ms)
        return True
        
    except Exception as e:
        validation_details['error'] = f'exception: {str(e)}'
        duration_ms = (time.time() - start_time) * 1000
        log_validation(url, False, 'security_check',
                      details=validation_details, duration_ms=duration_ms)
        record_validation(url, False, duration_ms, error_type='exception')
        return False


def normalize_url_rfc3986(url: str) -> Optional[str]:
    """
    Normalize URL according to RFC 3986 standards.
    
    This function performs:
    - Unicode normalization (NFKC)
    - Control character removal
    - Proper percent-encoding
    - Case normalization for scheme and host
    - Default port removal
    - Path normalization
    
    Args:
        url: The URL string to normalize
        
    Returns:
        Optional[str]: Normalized URL or None if normalization fails
    """
    if not url or not isinstance(url, str):
        return None
    
    start_time = time.time()
    original_url = url
    changes_made = []
    
    try:
        # Unicode normalization
        normalized = unicodedata.normalize('NFKC', url)
        if normalized != url:
            changes_made.append('unicode_normalization')
            url = normalized
        
        # Remove control characters
        clean_url = ''.join(char for char in url if ord(char) >= 32)
        if clean_url != url:
            changes_made.append('control_char_removal')
            url = clean_url
        
        # Parse URL
        parsed = urlparse(url)
        
        # Normalize scheme and host to lowercase
        scheme = parsed.scheme.lower() if parsed.scheme else ''
        hostname = parsed.hostname.lower() if parsed.hostname else ''
        
        if parsed.scheme and parsed.scheme != scheme:
            changes_made.append('scheme_lowercase')
        if parsed.hostname and parsed.hostname != hostname:
            changes_made.append('hostname_lowercase')
        
        # Remove default ports
        port = parsed.port
        if ((scheme == 'http' and port == 80) or
                (scheme == 'https' and port == 443)):
            netloc = hostname
            changes_made.append('default_port_removal')
        elif port:
            netloc = f"{hostname}:{port}"
        else:
            netloc = hostname
        
        # Add username/password if present
        if parsed.username:
            auth = parsed.username
            if parsed.password:
                auth += f":{parsed.password}"
            netloc = f"{auth}@{netloc}"
        
        # Normalize path
        path = parsed.path or '/'
        # Remove duplicate slashes
        normalized_path = re.sub(r'/+', '/', path)
        if normalized_path != path:
            changes_made.append('duplicate_slash_removal')
            path = normalized_path
        # Properly encode path
        encoded_path = quote(unquote(path), safe='/~')
        if encoded_path != path:
            changes_made.append('path_encoding')
            path = encoded_path
        
        # Properly encode query and fragment
        query = quote(unquote(parsed.query), safe='=&') if parsed.query else ''
        fragment = (quote(unquote(parsed.fragment), safe='')
                    if parsed.fragment else '')
        
        # Reconstruct URL
        normalized = urlunparse((scheme, netloc, path, '', query, fragment))
        
        # Log sanitization
        duration_ms = (time.time() - start_time) * 1000
        log_sanitization(original_url, normalized, changes_made,
                        duration_ms=duration_ms)
        
        return normalized
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_validation(url, False, 'normalization',
                      details={'error': str(e)}, duration_ms=duration_ms)
        return None


def sanitize_url_for_storage(url: str) -> Optional[str]:
    """
    Prepare URLs for safe storage with comprehensive sanitization.
    
    This function combines security validation, RFC 3986 normalization,
    and additional safety checks to ensure URLs are safe for storage.
    
    Args:
        url: The URL string to sanitize
        
    Returns:
        Optional[str]: Sanitized URL ready for storage or None if invalid
    """
    if not url or not isinstance(url, str):
        return None
    
    # First, apply basic sanitization
    url = sanitize_url(url)
    if not url:
        return None
    
    # Normalize according to RFC 3986
    url = normalize_url_rfc3986(url)
    if not url:
        return None
    
    # Security validation
    if not is_secure_url(url):
        return None
    
    # Final format validation
    if not validate_url_format(url):
        return None
    
    return url


def validate_url_batch(urls: List[str], check_accessibility: bool = False,
                       max_workers: int = 10) -> Dict[str, Dict[str, any]]:
    """
    Validate multiple URLs efficiently with optional accessibility checking.
    
    This function uses threading for parallel processing and includes
    caching to improve performance for repeated validations.
    
    Args:
        urls: List of URL strings to validate
        check_accessibility: Whether to check if URLs are accessible
        max_workers: Maximum number of threads for parallel processing
        
    Returns:
        Dict[str, Dict[str, any]]: Dictionary mapping URLs to their
            validation results. Each result contains:
            - 'valid': bool - Whether URL format is valid
            - 'secure': bool - Whether URL passes security checks
            - 'normalized': str or None - Normalized URL
            - 'accessible': bool or None - Accessibility status (if checked)
            - 'error': str or None - Error message if validation failed
    """
    results = {}
    
    def validate_single_url(url: str) -> Tuple[str, Dict[str, any]]:
        """Validate a single URL and return results."""
        result = {
            'valid': False,
            'secure': False,
            'normalized': None,
            'accessible': None,
            'error': None
        }
        
        try:
            # Check cache first
            cached_result = _get_cached_validation(url)
            if cached_result is not None and not check_accessibility:
                result['valid'] = cached_result
                result['secure'] = cached_result
                if cached_result:
                    result['normalized'] = normalize_url_rfc3986(url)
                return url, result
            
            # Validate format
            if not validate_url_format(url):
                result['error'] = 'Invalid URL format'
                _cache_validation(url, False)
                return url, result
            
            # Security validation
            if not is_secure_url(url):
                result['error'] = 'URL failed security validation'
                _cache_validation(url, False)
                return url, result
            
            # Normalize URL
            normalized = normalize_url_rfc3986(url)
            if not normalized:
                result['error'] = 'URL normalization failed'
                _cache_validation(url, False)
                return url, result
            
            result['valid'] = True
            result['secure'] = True
            result['normalized'] = normalized
            
            # Check accessibility if requested
            if check_accessibility:
                result['accessible'] = check_url_accessibility(normalized)
            
            _cache_validation(url, True)
            
        except Exception as e:
            result['error'] = f'Validation error: {str(e)}'
            _cache_validation(url, False)
        
        return url, result
    
    # Process URLs in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(validate_single_url, url): url
                   for url in urls}
        
        for future in as_completed(futures):
            url, result = future.result()
            results[url] = result
    
    return results


def _get_cached_validation(url: str) -> Optional[bool]:
    """
    Get cached validation result if available and not expired.
    
    Args:
        url: The URL to check
        
    Returns:
        Optional[bool]: Cached validation result or None if not cached/expired
    """
    with _cache_lock:
        if url in _validation_cache:
            is_valid, timestamp = _validation_cache[url]
            if time.time() - timestamp < CACHE_TTL:
                return is_valid
            else:
                # Remove expired entry
                del _validation_cache[url]
    return None


def _cache_validation(url: str, is_valid: bool) -> None:
    """
    Cache validation result with timestamp.
    
    Args:
        url: The URL that was validated
        is_valid: Validation result to cache
    """
    with _cache_lock:
        _validation_cache[url] = (is_valid, time.time())
        
        # Limit cache size (simple FIFO eviction)
        if len(_validation_cache) > 10000:
            # Remove oldest 1000 entries
            sorted_items = sorted(_validation_cache.items(),
                                  key=lambda x: x[1][1])
            for key, _ in sorted_items[:1000]:
                del _validation_cache[key]


def validate_url_format(url: str) -> bool:
    """
    Validate if a URL has a proper format.
    
    Args:
        url: The URL string to validate
        
    Returns:
        bool: True if URL format is valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    # Simplified URL pattern that accepts most valid domains
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:'
        # domain.tld
        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,10}'
        r'|localhost'  # or localhost
        r'|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'  # or IP address
        r')'
        r'(?::\d+)?'  # optional port
        r'(?:/[^\s]*)?$',  # optional path
        re.IGNORECASE
    )
    
    return bool(url_pattern.match(url))


def sanitize_url(url: str) -> Optional[str]:
    """
    Sanitize and fix common URL formatting issues.
    
    Args:
        url: The URL string to sanitize
        
    Returns:
        Optional[str]: Sanitized URL or None if URL cannot be fixed
    """
    if not url or not isinstance(url, str):
        return None
    
    # Strip whitespace
    url = url.strip()
    
    if not url:
        return None
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        # Default to https for security
        url = 'https://' + url
    
    # Parse and reconstruct URL to normalize it
    try:
        parsed = urlparse(url)
        
        # Ensure we have a valid scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return None
        
        # Reconstruct the URL to normalize it
        sanitized = urlunparse(parsed)
        
        # Final validation
        if validate_url_format(sanitized):
            return sanitized
        else:
            return None
            
    except Exception:
        return None


def check_url_accessibility(url: str, timeout: int = 5) -> bool:
    """
    Check if a URL is accessible by making a HEAD request.
    
    Args:
        url: The URL to check
        timeout: Request timeout in seconds
        
    Returns:
        bool: True if URL is accessible, False otherwise
    """
    if not validate_url_format(url):
        log_validation(url, False, 'accessibility_check',
                      details={'error': 'invalid_format'})
        return False
    
    start_time = time.time()
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        is_accessible = response.status_code < 400
        duration_ms = (time.time() - start_time) * 1000
        
        # Log the result
        details = {'status_code': response.status_code}
        log_validation(url, is_accessible, 'accessibility_check',
                      details=details, duration_ms=duration_ms)
        
        # Record metrics
        if not is_accessible:
            record_validation(url, False, duration_ms,
                            error_type=f'http_{response.status_code}')
        else:
            record_validation(url, True, duration_ms)
            
        return is_accessible
    except requests.RequestException as e:
        duration_ms = (time.time() - start_time) * 1000
        error_type = type(e).__name__
        log_validation(url, False, 'accessibility_check',
                      details={'error': str(e), 'error_type': error_type},
                      duration_ms=duration_ms)
        record_validation(url, False, duration_ms, error_type='request_failed')
        return False


def extract_domain(url: str) -> Optional[str]:
    """
    Extract the domain name from a URL for display purposes.
    
    Args:
        url: The URL to extract domain from
        
    Returns:
        Optional[str]: Domain name or None if extraction fails
    """
    if not url or not isinstance(url, str):
        return None
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Remove www. prefix for cleaner display
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain if domain else None
        
    except Exception:
        return None


def validate_and_sanitize_url(url: str,
                              check_accessibility: bool = False
                              ) -> Tuple[Optional[str], bool]:
    """
    Comprehensive URL validation and sanitization.
    
    Args:
        url: The URL to process
        check_accessibility: Whether to check if URL is accessible
        
    Returns:
        Tuple[Optional[str], bool]: (sanitized_url, is_valid)
            - sanitized_url: The cleaned URL or None if invalid
            - is_valid: True if URL is valid and optionally accessible
    """
    if not url:
        return None, False
    
    # First sanitize the URL
    sanitized = sanitize_url(url)
    
    if not sanitized:
        return None, False
    
    # Check accessibility if requested
    if check_accessibility:
        is_accessible = check_url_accessibility(sanitized)
        return sanitized, is_accessible
    
    return sanitized, True


def format_url_for_display(url: str, max_length: int = 50) -> str:
    """
    Format a URL for display purposes, truncating if necessary.
    
    Args:
        url: The URL to format
        max_length: Maximum length for display
        
    Returns:
        str: Formatted URL for display
    """
    if not url:
        return "No URL available"
    
    domain = extract_domain(url)
    if not domain:
        # Fallback to truncated URL
        if len(url) <= max_length:
            return url
        return url[:max_length-3] + "..."
    
    # If domain is short enough, show full URL
    if len(url) <= max_length:
        return url
    
    # Show domain with indication of truncation
    return f"{domain}/..."


def check_urls_accessibility_parallel(urls: List[str], timeout: int = 5,
                                      max_workers: int = 10
                                      ) -> Dict[str, bool]:
    """
    Check accessibility of multiple URLs in parallel.
    
    This function uses threading to check multiple URLs concurrently,
    significantly improving performance for batch operations.
    
    Args:
        urls: List of URLs to check
        timeout: Request timeout in seconds for each URL
        max_workers: Maximum number of concurrent threads
        
    Returns:
        Dict[str, bool]: Dictionary mapping URLs to their accessibility status
    """
    results = {}
    
    def check_single_url(url: str) -> Tuple[str, bool]:
        """Check accessibility of a single URL."""
        is_accessible = check_url_accessibility(url, timeout)
        return url, is_accessible
    
    # Process URLs in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_single_url, url): url
                   for url in urls}
        
        for future in as_completed(futures):
            url, is_accessible = future.result()
            results[url] = is_accessible
    
    return results