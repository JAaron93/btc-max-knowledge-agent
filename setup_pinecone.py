#!/usr/bin/env python3
"""
Setup script for Pinecone RAG system with Bitcoin knowledge base

Prerequisites:
    Install the package in development mode first:
    pip install -e .
"""

import logging
import sys
from requests.exceptions import RequestException, ConnectionError, Timeout
from urllib3.exceptions import HTTPError

from btc_max_knowledge_agent.knowledge.data_collector import BitcoinDataCollector
from btc_max_knowledge_agent.retrieval.pinecone_client import PineconeClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('setup_pinecone.log')
    ]
)
logger = logging.getLogger(__name__)


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

        if not results:
            print("⚠️  Warning: No results found from test query!")
            print("This may be due to index eventual consistency.")
            print("The index might need a few moments to become queryable.")
            print("Setup completed successfully, but please verify query results later.")
        print("Top 3 results:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result['title']} (score: {result['score']:.3f})")

    except (RequestException, ConnectionError, Timeout, HTTPError) as e:
        logger.error(f"Network/API error during setup: {e}")
        logger.error("This may indicate network connectivity issues or API service problems")
        logger.error("Please check your internet connection and API service status")
        raise
    except KeyError as e:
        logger.error(f"Configuration error - missing required key: {e}")
        logger.error("Make sure you have created a .env file with all required API keys")
        logger.error("Required keys: PINECONE_API_KEY, OPENAI_API_KEY")
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error(f"File system error: {e}")
        logger.error("Make sure all required files and directories exist")
        logger.error("Run: pip install -r requirements.txt to install dependencies")
        sys.exit(1)
    except ImportError as e:
        logger.error(f"Import error - missing dependency: {e}")
        logger.error("Make sure all requirements are installed")
        logger.error("Run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during setup: {e}")
        logger.error("This is an unexpected error. Please check the logs for details")
        logger.exception("Full stack trace:")
        sys.exit(1)


if __name__ == "__main__":
    main()
