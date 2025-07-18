from pinecone import Pinecone, ServerlessSpec
import time
import re
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from src.utils.config import Config

class PineconeClient:
    def __init__(self):
        Config.validate()
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=Config.PINECONE_API_KEY)
        
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
    
    def validate_and_sanitize_url(self, url: Optional[str]) -> Optional[str]:
        """Validate and sanitize URL, return None if invalid"""
        if not url or not isinstance(url, str):
            return None
        
        # Strip whitespace
        url = url.strip()
        if not url:
            return None
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            # Parse URL to validate structure
            parsed = urlparse(url)
            
            # Check if URL has valid scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return None
            
            # Basic domain validation
            if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', parsed.netloc):
                return None
            
            return url
        except Exception:
            return None
    
    def upsert_documents(self, documents: List[Dict[str, Any]]):
        """Upsert documents to Pinecone index with URL metadata support"""
        index = self.get_index()
        
        vectors = []
        for i, doc in enumerate(documents):
            # Validate and sanitize URL if provided
            url = self.validate_and_sanitize_url(doc.get('url'))
            
            # Prepare metadata with URL field
            metadata = {
                'title': doc.get('title', ''),
                'source': doc.get('source', ''),
                'category': doc.get('category', ''),
                'content': doc['content'][:1000],  # Store first 1000 chars in metadata
                'url': url or ''  # Include URL field, empty string if None
            }
            
            # Add published date if available
            if doc.get('published'):
                metadata['published'] = doc['published']
            
            # Prepare vector for upsert
            vector = {
                'id': doc.get('id', f"doc_{i}"),
                'values': doc.get('embedding', []),  # Use provided embedding
                'metadata': metadata
            }
            vectors.append(vector)
        
        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            index.upsert(vectors=batch)
            print(f"Upserted batch {i//batch_size + 1}/{(len(vectors)-1)//batch_size + 1}")
    
    def query_similar(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """Query for similar documents with URL metadata support"""
        index = self.get_index()
        
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
                'content': match['metadata'].get('content', ''),
                'url': match['metadata'].get('url', ''),  # Include URL in results
                'published': match['metadata'].get('published', '')  # Include published date if available
            }
            for match in results['matches']
        ]
    
    def get_index_stats(self):
        """Get index statistics"""
        index = self.get_index()
        return index.describe_index_stats()