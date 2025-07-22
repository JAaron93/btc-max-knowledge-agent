#!/usr/bin/env python3
"""
Demonstration script for PineconeAssistantAgent URL metadata functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from btc_max_knowledge_agent.agents.pinecone_assistant_agent import (
    PineconeAssistantAgent,
)
from btc_max_knowledge_agent.knowledge.data_collector import (
    BitcoinDataCollector,
)

def demo_url_metadata_functionality():
    """Demonstrate URL metadata functionality"""
    print("🚀 PineconeAssistantAgent URL Metadata Demo")
    print("=" * 50)
    
    try:
        # Initialize components
        print("📊 Initializing Data Collector...")
        data_collector = BitcoinDataCollector()
        
        print("🤖 Initializing Pinecone Assistant Agent...")
        assistant_agent = PineconeAssistantAgent()
        
        # Collect sample documents
        print("\n📚 Collecting Bitcoin documents with URL metadata...")
        bitcoin_docs = data_collector.collect_bitcoin_basics()
        genius_docs = data_collector.collect_genius_act_info()
        dapp_docs = data_collector.collect_dapp_information()
        
        all_docs = bitcoin_docs + genius_docs + dapp_docs
        
        print(f"✅ Collected {len(all_docs)} documents")
        
        # Display document information
        print("\n📋 Document Information:")
        for doc in all_docs:
            print(f"  • {doc['title']}")
            print(f"    URL: {doc.get('url', 'No URL')}")
            print(f"    Category: {doc['category']}")
            print()
        
        # Demonstrate URL validation
        print("🔍 URL Validation Examples:")
        test_urls = [
            'https://bitcoin.org/bitcoin.pdf',
            'bitcoin.org/bitcoin.pdf',  # Missing protocol
            'invalid-url',
            None
        ]
        
        for url in test_urls:
            validated = assistant_agent._validate_and_sanitize_url(url)
            print(f"  • Input: {url}")
            print(f"    Validated: {validated}")
            print()
        
        # Demonstrate document formatting for upload
        print("📤 Document Upload Format Example:")
        sample_doc = all_docs[0]
        
        # Show how the document would be formatted for upload
        formatted_doc = {
            "id": sample_doc.get('id', ''),
            "text": sample_doc.get('content', ''),
            "metadata": {
                "title": sample_doc.get('title', ''),
                "source": sample_doc.get('source', ''),
                "category": sample_doc.get('category', ''),
                "url": assistant_agent._validate_and_sanitize_url(sample_doc.get('url', '')) or '',
                "published": sample_doc.get('published', '')
            }
        }
        
        print(f"Document ID: {formatted_doc['id']}")
        print(f"Title: {formatted_doc['metadata']['title']}")
        print(f"URL: {formatted_doc['metadata']['url']}")
        print(f"Source: {formatted_doc['metadata']['source']}")
        print(f"Category: {formatted_doc['metadata']['category']}")
        print()
        
        # Demonstrate source formatting
        print("📖 Source Formatting Example:")
        mock_citations = [
            {
                'id': 'bitcoin_whitepaper',
                'text': 'Bitcoin is a peer-to-peer electronic cash system...',
                'score': 0.95,
                'metadata': {
                    'title': 'Bitcoin: A Peer-to-Peer Electronic Cash System',
                    'source': 'bitcoin.org',
                    'category': 'fundamentals',
                    'url': 'https://bitcoin.org/bitcoin.pdf',
                    'published': '2008-10-31'
                }
            }
        ]
        
        formatted_sources = assistant_agent._format_sources_with_urls(mock_citations)
        
        for source in formatted_sources:
            print(f"  • {source['title']}")
            print(f"    URL: {source['url']}")
            print(f"    Score: {source['score']}")
            print(f"    Published: {source['published']}")
            print()
        
        print("✅ Demo completed successfully!")
        print("\n💡 Key Features Demonstrated:")
        print("  • URL validation and sanitization")
        print("  • Document formatting with URL metadata")
        print("  • Source formatting with URL information")
        print("  • Integration with data collector")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demo_url_metadata_functionality()