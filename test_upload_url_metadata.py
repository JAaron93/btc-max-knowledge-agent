#!/usr/bin/env python3
"""
Test script to verify URL metadata functionality in upload script
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from upload_to_pinecone_assistant import _is_valid_url, _get_display_name

def test_url_validation():
    """Test URL validation function"""
    print("🧪 Testing URL Validation")
    print("=" * 30)
    
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
        status = "✅" if result == expected else "❌"
        print(f"{status} {url} -> {result} (expected: {expected})")
    
    print()

def test_display_name():
    """Test display name function"""
    print("🧪 Testing Display Name Generation")
    print("=" * 35)
    
    test_cases = [
        ("https://cointelegraph.com/rss", "Cointelegraph.Com"),
        ("https://www.coindesk.com/feed", "Coindesk.Com"),
        ("bitcoin.org", "bitcoin.org"),
        ("", "View Source"),
        (None, "View Source"),
    ]
    
    for source, expected in test_cases:
        result = _get_display_name(source)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{source}' -> '{result}' (expected: '{expected}')")
    
    print()

def test_file_generation():
    """Test that files are generated with proper URL metadata"""
    print("🧪 Testing File Generation with URL Metadata")
    print("=" * 45)
    
    # Check if files exist and contain URL metadata
    upload_dir = "data/upload_files"
    test_files = [
        "bitcoin_fundamentals.txt",
        "bitcoin_news.txt",
        "bitcoin_overview.txt"
    ]
    
    for filename in test_files:
        filepath = os.path.join(upload_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for URL metadata elements
            has_source_url = "**Source URL:**" in content
            has_original_article = "**Original Article:**" in content
            has_direct_link = "**Direct Link:**" in content
            has_metadata_section = "### Document Metadata" in content
            
            print(f"✅ {filename}:")
            print(f"   - Source URL field: {'✅' if has_source_url else '❌'}")
            print(f"   - Original Article link: {'✅' if has_original_article else '❌'}")
            print(f"   - Direct Link: {'✅' if has_direct_link else '❌'}")
            print(f"   - Metadata section: {'✅' if has_metadata_section else '❌'}")
        else:
            print(f"❌ {filename}: File not found")
    
    print()

def main():
    print("🚀 URL Metadata Test Suite")
    print("=" * 50)
    
    test_url_validation()
    test_display_name()
    test_file_generation()
    
    print("✅ All tests completed!")

if __name__ == "__main__":
    main()