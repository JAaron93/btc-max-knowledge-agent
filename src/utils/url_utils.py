"""
URL validation and sanitization utilities for the Bitcoin knowledge agent.

This module provides functions to validate, sanitize, and process URLs
for use in the Pinecone vector database metadata.
"""

import re
import urllib.parse
from typing import Optional, Tuple
import requests
from urllib.parse import urlparse, urlunparse


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
        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,10}'  # domain.tld
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
        return False
    
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code < 400
    except Exception:
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


def validate_and_sanitize_url(url: str, check_accessibility: bool = False) -> Tuple[Optional[str], bool]:
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