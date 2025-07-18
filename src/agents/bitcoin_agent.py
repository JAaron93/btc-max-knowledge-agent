from typing import List, Dict, Any
from src.retrieval.pinecone_client import PineconeClient
from src.utils.config import Config

class BitcoinKnowledgeAgent:
    def __init__(self):
        self.pinecone_client = PineconeClient()
        
    def answer_question(self, question_embedding: List[float], max_context_docs: int = 5) -> Dict[str, Any]:
        """Retrieve relevant documents for a question using RAG with Bitcoin knowledge base"""
        
        # Retrieve relevant documents
        relevant_docs = self.pinecone_client.query_similar(
            query_embedding=question_embedding, 
            top_k=max_context_docs
        )
        
        if not relevant_docs:
            return {
                'documents': [],
                'message': "No relevant information found in the Bitcoin knowledge base."
            }
        
        # Return the relevant documents with URL metadata
        return {
            'documents': relevant_docs,
            'message': f"Found {len(relevant_docs)} relevant documents"
        }
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        return self.pinecone_client.get_index_stats()