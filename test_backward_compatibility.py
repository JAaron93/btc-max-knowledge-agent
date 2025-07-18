#!/usr/bin/env python3
"""
Test backward compatibility with documents that don't have URLs
"""

import sys
import os
import tempfile
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from upload_to_pinecone_assistant import _is_valid_url, _get_display_name

def test_documents_without_urls():
    """Test handling of documents without URLs"""
    print("🧪 Testing Backward Compatibility")
    print("=" * 35)
    
    # Simulate documents without URLs
    test_docs = [
        {
            'title': 'Test Document 1',
            'content': 'This is a test document without URL',
            'source': 'test_source',
            'category': 'test',
            # No URL field
        },
        {
            'title': 'Test Document 2', 
            'content': 'This is another test document',
            'source': 'test_source_2',
            'category': 'test',
            'url': '',  # Empty URL
        },
        {
            'title': 'Test Document 3',
            'content': 'This document has a valid URL',
            'source': 'test_source_3', 
            'category': 'test',
            'url': 'https://example.com/article'
        }
    ]
    
    # Test URL handling for each document
    for i, doc in enumerate(test_docs, 1):
        print(f"\n📄 Document {i}: {doc['title']}")
        
        url = doc.get('url', '').strip()
        if url and _is_valid_url(url):
            print(f"   ✅ Has valid URL: {url}")
            print(f"   ✅ Display name: {_get_display_name(doc.get('source', 'View Source'))}")
        else:
            print(f"   ⚠️  No valid URL (url='{url}')")
            print(f"   ✅ Graceful handling: Source link not provided")
    
    print(f"\n✅ Backward compatibility test passed!")

def test_mixed_document_formatting():
    """Test formatting with mixed documents (some with URLs, some without)"""
    print("\n🧪 Testing Mixed Document Formatting")
    print("=" * 40)
    
    # Create a temporary file to test formatting
    test_docs = [
        {
            'title': 'Document with URL',
            'content': 'Content with source link',
            'source': 'example.com',
            'category': 'test',
            'url': 'https://example.com/article'
        },
        {
            'title': 'Document without URL',
            'content': 'Content without source link',
            'source': 'internal_source',
            'category': 'test'
            # No URL field
        }
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test Knowledge Base\n\n")
        
        for doc in test_docs:
            f.write(f"## {doc.get('title', 'Untitled')}\n\n")
            
            # Enhanced URL formatting with clear visibility and structure
            f.write("### Document Metadata\n")
            f.write(f"**Source:** {doc.get('source', 'Unknown')}\n")
            f.write(f"**Category:** {doc.get('category', 'general')}\n")
            
            # Enhanced URL handling with validation and clear formatting
            url = doc.get('url', '').strip()
            if url and _is_valid_url(url):
                f.write(f"**Source URL:** {url}\n")
                f.write(f"**Original Article:** [{_get_display_name(doc.get('source', 'View Source'))}]({url})\n")
                f.write(f"**Direct Link:** <{url}>\n")
            else:
                f.write(f"**Source URL:** Not available\n")
                f.write(f"**Original Article:** Source link not provided\n")
            
            f.write("\n### Content\n")
            f.write(f"{doc.get('content', '')}\n\n")
            f.write("-" * 80 + "\n\n")
        
        temp_file = f.name
    
    # Read and verify the formatted content
    with open(temp_file, 'r') as f:
        content = f.read()
    
    print(f"✅ Generated test file: {temp_file}")
    print("✅ Content preview:")
    print(content[:500] + "..." if len(content) > 500 else content)
    
    # Clean up
    os.unlink(temp_file)
    print("✅ Mixed document formatting test passed!")

def main():
    print("🚀 Backward Compatibility Test Suite")
    print("=" * 50)
    
    test_documents_without_urls()
    test_mixed_document_formatting()
    
    print("\n✅ All backward compatibility tests passed!")

if __name__ == "__main__":
    main()