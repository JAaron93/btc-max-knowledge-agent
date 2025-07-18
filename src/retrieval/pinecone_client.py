from pinecone import Pinecone, ServerlessSpec
import google.generativeai as genai
import time
from typing import List, Dict, Any
from src.utils.config import Config

class PineconeClient:
    def __init__(self):
        Config.validate()
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=Config.PINECONE_API_KEY)
        
        # Initialize Gemini for embeddings
        print("Initializing Gemini for embeddings...")
        genai.configure(api_key=Config.GEMINI_API_KEY)
        
        self.index_name = Config.PINECONE_INDEX_NAME
        self.dimension = Config.EMBEDDING_DIMENSION
        
    def create_index(self):
        """Create Pinecone index if it doesn't exist"""
        if self.index_name not in self.pc.list_indexes().names():
            print(f"Creating index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            
            # Wait for index to be ready
            while not self.pc.describe_index(self.index_name).status['ready']:
                time.sleep(1)
            print(f"Index {self.index_name} is ready!")
        else:
            print(f"Index {self.index_name} already exists")
    
    def get_index(self):
        """Get the Pinecone index"""
        return self.pc.Index(self.index_name)
    
    def create_embedding(self, text: str) -> List[float]:
        """Create embedding using Gemini"""
        result = genai.embed_content(
            model=Config.EMBEDDING_MODEL,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    
    def upsert_documents(self, documents: List[Dict[str, Any]]):
        """Upsert documents to Pinecone index"""
        index = self.get_index()
        
        vectors = []
        for i, doc in enumerate(documents):
            # Create embedding for the document content
            embedding = self.create_embedding(doc['content'])
            
            # Prepare vector for upsert
            vector = {
                'id': doc.get('id', f"doc_{i}"),
                'values': embedding,
                'metadata': {
                    'title': doc.get('title', ''),
                    'source': doc.get('source', ''),
                    'category': doc.get('category', ''),
                    'content': doc['content'][:1000]  # Store first 1000 chars in metadata
                }
            }
            vectors.append(vector)
        
        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            index.upsert(vectors=batch)
            print(f"Upserted batch {i//batch_size + 1}/{(len(vectors)-1)//batch_size + 1}")
    
    def query_similar(self, query: str, top_k: int = 5) -> List[Dict]:
        """Query for similar documents"""
        index = self.get_index()
        
        # Create embedding for query (using query task type)
        query_embedding = self.create_query_embedding(query)
        
        # Query Pinecone
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        
        return [
            {
                'id': match['id'],
                'score': match['score'],
                'title': match['metadata'].get('title', ''),
                'source': match['metadata'].get('source', ''),
                'category': match['metadata'].get('category', ''),
                'content': match['metadata'].get('content', '')
            }
            for match in results['matches']
        ]
    
    def create_query_embedding(self, text: str) -> List[float]:
        """Create embedding for query using Gemini"""
        result = genai.embed_content(
            model=Config.EMBEDDING_MODEL,
            content=text,
            task_type="retrieval_query"
        )
        return result['embedding']
    
    def get_index_stats(self):
        """Get index statistics"""
        index = self.get_index()
        return index.describe_index_stats()