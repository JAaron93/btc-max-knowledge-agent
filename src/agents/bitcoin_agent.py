from typing import List, Dict, Any
from src.retrieval.pinecone_client import PineconeClient
from anthropic import Anthropic
from src.utils.config import Config

class BitcoinKnowledgeAgent:
    def __init__(self):
        self.pinecone_client = PineconeClient()
        self.anthropic_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        
    def answer_question(self, question: str, max_context_docs: int = 5) -> str:
        """Answer a question using RAG with Bitcoin knowledge base"""
        
        # Retrieve relevant documents
        relevant_docs = self.pinecone_client.query_similar(
            query=question, 
            top_k=max_context_docs
        )
        
        if not relevant_docs:
            return "I don't have enough information to answer that question about Bitcoin or blockchain technology."
        
        # Build context from retrieved documents
        context = "\n\n".join([
            f"Source: {doc['title']}\n{doc['content']}"
            for doc in relevant_docs
        ])
        
        # Create prompt for GPT
        system_prompt = """You are a knowledgeable Bitcoin and blockchain technology educator. 
        Use the provided context to answer questions accurately and educationally. 
        Focus on being helpful, accurate, and educational.
        If the context doesn't contain enough information, say so clearly.
        Always cite which sources you're drawing from when possible."""
        
        user_prompt = f"""Context from Bitcoin knowledge base:
        {context}
        
        Question: {question}
        
        Please provide a comprehensive answer based on the context above."""
        
        # Get response from Claude
        response = self.anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0.7,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        answer = response.content[0].text
        
        # Add source information
        sources = [doc['title'] for doc in relevant_docs]
        answer += f"\n\nSources consulted: {', '.join(sources[:3])}"
        
        return answer
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        return self.pinecone_client.get_index_stats()