#!/usr/bin/env python3
"""
Upload Bitcoin documents to Pinecone Assistant via web interface
"""

import os
# Remove.  Install the project with:
#   pip install -e .
import re
import sys
from urllib.parse import urlparse

from btc_max_knowledge_agent.knowledge.data_collector import \
    BitcoinDataCollector


def _is_valid_url(url: str) -> bool:
    """Validate URL format and basic structure"""
    if not url or not isinstance(url, str):
        return False

    # Basic URL pattern validation
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    try:
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(url_pattern.match(url))
    except Exception:
        return False


def _get_display_name(source: str) -> str:
    """Get a clean display name for the source"""
    if not source:
        return "View Source"

    # Clean up common RSS feed URLs to be more readable
    if source.startswith("http"):
        try:
            parsed = urlparse(source)
            domain = parsed.netloc.replace("www.", "")
            return domain.title()
        except Exception:
            return source

    return source


def create_upload_files():
    """Create text files for upload to Pinecone Assistant"""

    print("📚 Creating Bitcoin Knowledge Files for Upload")
    print("=" * 50)

    # Collect documents
    collector = BitcoinDataCollector()
    documents = collector.collect_all_documents(max_news_articles=30)

    if not documents:
        print("❌ No documents collected")
        return

    # Create upload directory
    upload_dir = "data/upload_files"
    os.makedirs(upload_dir, exist_ok=True)

    # Group documents by category
    categories = {}
    for doc in documents:
        category = doc.get("category", "general")
        if category not in categories:
            categories[category] = []
        categories[category].append(doc)

    # Create files for each category
    file_count = 0
    for category, docs in categories.items():
        # sanitize category name for use in filenames
        safe = re.sub(r"[^0-9A-Za-z._-]+", "_", category.strip().lower())
        filename = f"{upload_dir}/bitcoin_{safe}.txt"
        if category != safe:
            print(f"ℹ️  Normalised filename for category '{category}' → '{safe}'")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# Bitcoin Knowledge Base - {category.title()}\n\n")

            for doc in docs:
                f.write(f"## {doc.get('title', 'Untitled')}\n\n")

                # Enhanced URL formatting with clear visibility and structure
                f.write("### Document Metadata\n")
                f.write(f"**Source:** {doc.get('source', 'Unknown')}\n")
                f.write(f"**Category:** {doc.get('category', 'general')}\n")

                # Enhanced URL handling with validation and clear formatting
                url = doc.get("url", "").strip()
                if url and _is_valid_url(url):
                    f.write(f"**Source URL:** {url}\n")
                    f.write(
                        f"**Original Article:** [{_get_display_name(doc.get('source', 'View Source'))}]({url})\n"
                    )
                    f.write(f"**Direct Link:** <{url}>\n")
                else:
                    f.write("**Source URL:** Not available\n")
                    f.write("**Original Article:** Source link not provided\n")

                # Add publication date if available (for RSS articles)
                if doc.get("published"):
                    f.write(f"**Published:** {doc.get('published')}\n")

                f.write("\n### Content\n")
                f.write(f"{doc.get('content', '')}\n\n")
                f.write("-" * 80 + "\n\n")

        file_count += 1
        print(f"✅ Created: {filename} ({len(docs)} documents)")

    # Create a comprehensive overview file with enhanced URL metadata
    overview_file = f"{upload_dir}/bitcoin_overview.txt"
    with open(overview_file, "w", encoding="utf-8") as f:
        f.write("# Bitcoin and Blockchain Knowledge Base\n\n")
        f.write("This knowledge base contains comprehensive information about:\n\n")
        f.write("## Topics Covered\n\n")
        f.write("- **Bitcoin Fundamentals**: Core concepts, whitepaper, technology\n")
        f.write(
            "- **Blockchain Technology**: Distributed ledgers, consensus, security\n"
        )
        f.write("- **Lightning Network**: Layer-2 scaling, payment channels\n")
        f.write("- **Decentralized Applications (dApps)**: Smart contracts, DeFi\n")
        f.write("- **Regulation**: GENIUS Act and cryptocurrency legislation\n")
        f.write(
            "- **News & Updates**: Latest developments in the Bitcoin ecosystem\n\n"
        )

        f.write("## Document Categories\n\n")
        for category, docs in categories.items():
            f.write(f"- **{category.title()}**: {len(docs)} documents\n")

        f.write(f"\n**Total Documents**: {len(documents)}\n")
        f.write(
            f"**Last Updated**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        # Add URL metadata statistics
        f.write("## Source Attribution\n\n")
        url_count = sum(1 for doc in documents if doc.get("url", "").strip())
        f.write(f"- **Documents with Source URLs**: {url_count}/{len(documents)}\n")
        f.write(f"- **URL Coverage**: {(url_count/len(documents)*100):.1f}%\n\n")

        # Add key concepts summary
        f.write("## Key Concepts Summary\n\n")
        f.write("### Bitcoin\n")
        f.write(
            "Bitcoin is a peer-to-peer electronic cash system that allows online payments without financial institutions. It uses blockchain technology for security and decentralization.\n\n"
        )

        f.write("### Lightning Network\n")
        f.write(
            "A Layer-2 payment protocol on Bitcoin enabling fast, low-cost transactions through payment channels.\n\n"
        )

        f.write("### dApps\n")
        f.write(
            "Decentralized applications running on blockchain networks, offering services without central control.\n\n"
        )

        f.write("### GENIUS Act\n")
        f.write(
            "Legislation promoting blockchain innovation and cryptocurrency adoption in the United States.\n\n"
        )

    file_count += 1
    print(f"✅ Created: {overview_file} (overview)")

    print("\n📋 Upload Instructions:")
    print("=" * 50)
    print("1. Go to https://app.pinecone.io")
    print("2. Navigate to your 'genius' assistant")
    print("3. Look for 'Upload Files' or 'Add Documents' option")
    print(f"4. Upload all {file_count} files from: {upload_dir}/")
    print("5. Wait for processing to complete")
    print("6. Test the MCP connection again")

    print(f"\n📁 Files created in {upload_dir}/:")
    for filename in os.listdir(upload_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(upload_dir, filename)
            size = os.path.getsize(filepath)
            print(f"   - {filename} ({size:,} bytes)")

    return upload_dir


def main():
    print("🚀 Bitcoin Knowledge Base File Creator")
    print("=" * 50)

    try:
        upload_dir = create_upload_files()

        if upload_dir:
            print(f"\n✅ Success! Files ready for upload in: {upload_dir}")
            print("\n🔄 After uploading to Pinecone Assistant:")
            print("   python test_mcp_tools.py  # Test the connection")
            print("   # The MCP tools should then work with your Bitcoin knowledge!")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
