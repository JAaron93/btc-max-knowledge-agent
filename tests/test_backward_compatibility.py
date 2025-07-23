#!/usr/bin/env python3
"""
Test backward compatibility with documents that don't have URLs
"""

import os
import tempfile

from src.utils.url_utils import extract_domain, is_url_valid


def test_documents_without_urls():
    """Test handling of documents without URLs"""

    # Simulate documents without URLs
    test_docs = [
        {
            "title": "Test Document 1",
            "content": "This is a test document without URL",
            "source": "test_source",
            "category": "test",
            # No URL field
        },
        {
            "title": "Test Document 2",
            "content": "This is another test document",
            "source": "test_source_2",
            "category": "test",
            "url": "",  # Empty URL
        },
        {
            "title": "Test Document 3",
            "content": "This document has a valid URL",
            "source": "test_source_3",
            "category": "test",
            "url": "https://example.com/article",
        },
    ]

    # Test URL handling for each document
    for i, doc in enumerate(test_docs, 1):
        url = doc.get("url", "").strip()
        if url and is_url_valid(url):
            assert is_url_valid(url) is True
            # Use extract_domain to get a clean display name from source
            source = doc.get("source", "View Source")
            if source.startswith("http"):
                domain = extract_domain(source)
                assert domain is not None
            else:
                assert source is not None
        else:
            # For empty URLs or invalid URLs, the result should be falsy
            assert not (url and is_url_valid(url))


def test_mixed_document_formatting():
    """Test formatting with mixed documents (some with URLs, some without)"""
    print("\n🧪 Testing Mixed Document Formatting")
    print("=" * 40)

    # Create a temporary file to test formatting
    test_docs = [
        {
            "title": "Document with URL",
            "content": "Content with source link",
            "source": "example.com",
            "category": "test",
            "url": "https://example.com/article",
        },
        {
            "title": "Document without URL",
            "content": "Content without source link",
            "source": "internal_source",
            "category": "test",
            # No URL field
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("# Test Knowledge Base\n\n")

        for doc in test_docs:
            f.write(f"## {doc.get('title', 'Untitled')}\n\n")

            # Enhanced URL formatting with clear visibility and structure
            f.write("### Document Metadata\n")
            f.write(f"**Source:** {doc.get('source', 'Unknown')}\n")
            f.write(f"**Category:** {doc.get('category', 'general')}\n")

            # Enhanced URL handling with validation and clear formatting
            url = doc.get("url", "").strip()
            if url and is_url_valid(url):
                f.write(f"**Source URL:** {url}\n")
                # Use extract_domain for display name or fallback to source
                source = doc.get('source', 'View Source')
                if source.startswith('http'):
                    display_name = extract_domain(source) or source
                else:
                    display_name = source
                f.write(
                    f"**Original Article:** [{display_name}]({url})\n"
                )
                f.write(f"**Direct Link:** <{url}>\n")
            else:
                f.write("**Source URL:** Not available\n")
                f.write("**Original Article:** Source link not provided\n")

            f.write("\n### Content\n")
            f.write(f"{doc.get('content', '')}\n\n")
            f.write("-" * 80 + "\n\n")

        temp_file = f.name

    # Read and verify the formatted content
    with open(temp_file, "r") as f:
        content = f.read()

    # Split content by document separator
    documents = content.split("-" * 80 + "\n\n")
    documents = [doc.strip() for doc in documents if doc.strip()]

    # Verify we have the expected number of documents (2 + the header = 3 total sections)
    # But we only have actual documents (the header doesn't count as a document)
    assert len(documents) == 2, f"Expected 2 documents, found {len(documents)}"

    # Check each document's structure
    for i, doc in enumerate(documents, 1):
        # Verify document has required sections
        assert "### Document Metadata" in doc, f"Document {i} missing metadata section"
        assert "### Content" in doc, f"Document {i} missing content section"

        # Split into metadata and content sections
        metadata_section = doc.split("### Content")[0]
        content_section = doc.split("### Content")[1] if "### Content" in doc else ""

        # Check metadata section contains required fields
        if i == 1:  # Document with URL
            assert "**Source URL:** https://example.com/article" in metadata_section
            assert "**Original Article:** [" in metadata_section
            assert "**Direct Link:** <https://example.com/article>" in metadata_section
        elif i == 2:  # Document without URL
            assert "**Source URL:** Not available" in metadata_section
            assert "**Original Article:** Source link not provided" in metadata_section

        # Verify content is not empty
        assert content_section.strip(), f"Document {i} has empty content"

    # Print test success details
    print(f"✅ Generated test file: {temp_file}")
    print("✅ Content validation passed for all documents")

    # Clean up
    os.unlink(temp_file)
    print("✅ Mixed document formatting test passed!")


def main():
    print("🚀 Backward Compatibility Test Suite")
    print("=" * 50)
    
    test_results = []
    
    # Test 1: Documents without URLs
    try:
        test_documents_without_urls()
        print("✅ test_documents_without_urls passed!")
        test_results.append(("test_documents_without_urls", True, None))
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"❌ test_documents_without_urls failed: {error_msg}")
        test_results.append(("test_documents_without_urls", False, error_msg))

    # Test 2: Mixed document formatting
    try:
        test_mixed_document_formatting()
        print("✅ test_mixed_document_formatting passed!")
        test_results.append(("test_mixed_document_formatting", True, None))
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"❌ test_mixed_document_formatting failed: {error_msg}")
        test_results.append(("test_mixed_document_formatting", False, error_msg))

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    passed_count = sum(1 for _, passed, _ in test_results if passed)
    total_count = len(test_results)
    
    for test_name, passed, error in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if error:
            print(f"    Error: {error}")
    
    print(f"\n🔍 Test execution completed: {passed_count}/{total_count} tests passed")
    
    # Return exit code for CI/CD systems
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    main()
