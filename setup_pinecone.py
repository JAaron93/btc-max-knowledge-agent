#!/usr/bin/env python3
"""
Setup script for Pinecone RAG system with Bitcoin knowledge base
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from btc_max_knowledge_agent.knowledge.data_collector import BitcoinDataCollector
from btc_max_knowledge_agent.retrieval.pinecone_client import PineconeClient


def main():
    print("🚀 Setting up Bitcoin Knowledge Base with Pinecone")
    print("=" * 50)

    try:
        # Initialize components
        print("1. Initializing Pinecone client...")
        pinecone_client = PineconeClient()

        print("2. Creating Pinecone index...")
        pinecone_client.create_index()

        print("3. Initializing data collector...")
        collector = BitcoinDataCollector()

        print("4. Collecting Bitcoin and blockchain documents...")
        documents = collector.collect_all_documents(max_news_articles=50)

        if not documents:
            print("❌ No documents collected. Exiting.")
            return

        print(f"5. Collected {len(documents)} documents")

        # Save documents locally
        print("6. Saving documents locally...")
        collector.save_documents(documents)

        # Upload to Pinecone
        print("7. Uploading documents to Pinecone...")
        pinecone_client.upsert_documents(documents)

        # Check index stats
        print("8. Checking index statistics...")
        stats = pinecone_client.get_index_stats()
        print(f"   Total vectors: {stats['total_vector_count']}")
        print(f"   Index fullness: {stats['index_fullness']}")

        print("\n✅ Setup complete!")
        print(f"   - {len(documents)} documents indexed")
        print(f"   - Index name: {pinecone_client.index_name}")
        print("   - Ready for queries!")

        # Test query
        print("\n🔍 Testing with sample query...")
        results = pinecone_client.query_similar("What is Bitcoin?", top_k=3)

        print("Top 3 results:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result['title']} (score: {result['score']:.3f})")

    except Exception as e:
        print(f"❌ Error during setup: {e}")
        print("Make sure you have:")
        print("1. Created a .env file with your API keys")
        print("2. Installed all requirements: pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
