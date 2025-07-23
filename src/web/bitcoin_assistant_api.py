#!/usr/bin/env python3
"""
Bitcoin Knowledge Assistant API using FastAPI and Pinecone Assistant
"""

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pinecone import Pinecone
from pinecone_plugins.assistant.models.chat import Message
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="Bitcoin Knowledge Assistant",
    description="AI-powered Bitcoin and blockchain knowledge assistant using Pinecone",
    version="1.0.0",
)


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict]
    raw_context: Optional[Dict] = None


class BitcoinAssistantService:
    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.assistant_name = "genius"  # From your screenshot

        if not self.api_key:
            raise ValueError("Missing PINECONE_API_KEY")

        # Initialize Pinecone client with assistant plugin
        self.pc = Pinecone(api_key=self.api_key)
        self.assistant = self.pc.assistant.Assistant(assistant_name=self.assistant_name)

    def get_assistant_response(self, question: str) -> Dict:
        """Get intelligent response from Pinecone Assistant"""
        try:
            # Create message for the assistant
            msg = Message(role="user", content=question)

            # Get response from Pinecone Assistant
            response = self.assistant.chat(messages=[msg])

            # Extract the response content and citations
            result = {
                "answer": response.message.content,
                "citations": (
                    response.citations if hasattr(response, "citations") else []
                ),
                "sources": [],
            }

            # Extract source information from citations
            if hasattr(response, "citations") and response.citations:
                for citation in response.citations:
                    if hasattr(citation, "references") and citation.references:
                        for ref in citation.references:
                            if hasattr(ref, "file") and ref.file:
                                result["sources"].append(
                                    {
                                        "name": ref.file.name,
                                        "type": "document",
                                        "pages": getattr(ref, "pages", []),
                                    }
                                )

            return result

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Assistant query failed: {str(e)}"
            )

    def format_assistant_response(self, response_data: Dict) -> str:
        """Format the assistant response for display"""
        answer = response_data.get("answer", "")
        sources = response_data.get("sources", [])

        if not answer:
            return "I don't have enough information in my knowledge base to answer that question about Bitcoin or blockchain technology."

        formatted_response = answer

        # Add source information if available
        if sources:
            unique_sources = []
            seen_sources = set()
            for source in sources:
                source_name = source.get("name", "Unknown")
                if source_name not in seen_sources:
                    seen_sources.add(source_name)
                    unique_sources.append(source_name)

            if unique_sources:
                formatted_response += (
                    f"\n\n**Sources:** {', '.join(unique_sources[:5])}"
                )

        return formatted_response


# Initialize service
try:
    bitcoin_service = BitcoinAssistantService()
except Exception as e:
    print(f"Failed to initialize Bitcoin Assistant Service: {e}")
    bitcoin_service = None


@app.get("/")
async def root():
    return {
        "message": "Bitcoin Knowledge Assistant API",
        "status": "running",
        "endpoints": ["/query", "/health", "/docs"],
    }


@app.get("/health")
async def health_check():
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Test Pinecone Assistant connection with a simple query
        test_response = bitcoin_service.get_assistant_response("What is Bitcoin?")

        return {
            "status": "healthy",
            "pinecone_assistant": "connected",
            "assistant_name": bitcoin_service.assistant_name,
            "test_response_received": bool(test_response.get("answer")),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")


@app.post("/query", response_model=QueryResponse)
async def query_bitcoin_knowledge(request: QueryRequest):
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Get response from Pinecone Assistant
        response_data = bitcoin_service.get_assistant_response(request.question)

        # Format the assistant response
        answer = bitcoin_service.format_assistant_response(response_data)

        # Extract sources from the response
        sources = response_data.get("sources", [])

        return QueryResponse(
            answer=answer,
            sources=sources,
            raw_context=None,  # Raw context removed for cleaner responses
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/sources")
async def list_available_sources():
    """List available sources in the knowledge base"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Get a broad context to see available sources
        context = bitcoin_service.get_assistant_response(
            "Bitcoin blockchain cryptocurrency"
        )

        sources = set()
        if "content" in context:
            for item in context["content"]:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    if "📄 **" in text:
                        source_name = (
                            text.split("📄 **")[1].split("**")[0]
                            if "📄 **" in text
                            else "Unknown"
                        )
                        sources.add(source_name)

        return {
            "available_sources": sorted(list(sources)),
            "total_sources": len(sources),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sources: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
