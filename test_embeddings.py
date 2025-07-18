#!/usr/bin/env python3
"""
Test script to verify Gemini embeddings are working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.retrieval.pinecone_client import PineconeClient

def main():
    print("🧪 Testing Gemini Embeddings")
    print("=" * 30)
    
    try:
        # Initialize client
        print("1. Initializing Pinecone client with Gemini...")
        client = PineconeClient()
        
        # Test embedding creation
        print("2. Testing document embedding...")
        test_text = "Bitcoin is a decentralized digital currency that operates without a central bank."
        doc_embedding = client.create_embedding(test_text)
        print(f"   Document embedding dimension: {len(doc_embedding)}")
        
        # Test query embedding
        print("3. Testing query embedding...")
        test_query = "What is Bitcoin?"
        query_embedding = client.create_query_embedding(test_query)
        print(f"   Query embedding dimension: {len(query_embedding)}")
        
        # Verify dimensions match config
        from src.utils.config import Config
        expected_dim = Config.EMBEDDING_DIMENSION
        print(f"4. Expected dimension: {expected_dim}")
        
        if len(doc_embedding) == expected_dim and len(query_embedding) == expected_dim:
            print("✅ Embeddings working correctly!")
            print(f"   Both embeddings have correct dimension: {expected_dim}")
        else:
            print("❌ Dimension mismatch!")
            print(f"   Doc: {len(doc_embedding)}, Query: {len(query_embedding)}, Expected: {expected_dim}")
        
        # Test similarity (basic check)
        import numpy as np
        similarity = np.dot(doc_embedding, query_embedding) / (np.linalg.norm(doc_embedding) * np.linalg.norm(query_embedding))
        print(f"5. Similarity between test doc and query: {similarity:.4f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure your .env file has GEMINI_API_KEY set correctly!")

if __name__ == "__main__":
    main()