import logging
from typing import Any, Dict, List

from btc_max_knowledge_agent.retrieval.pinecone_client import PineconeClient
from btc_max_knowledge_agent.utils.result_formatter import QueryResultFormatter


class BitcoinKnowledgeAgent:
    def __init__(self):
        self.pinecone_client = PineconeClient()

    def answer_question(
        self,
        question_embedding: List[float],
        max_context_docs: int = 5,
        query_text: str = "",
    ) -> Dict[str, Any]:
        """Retrieve relevant documents for a question using RAG with Bitcoin knowledge base"""

        # Retrieve relevant documents
        relevant_docs = self.pinecone_client.query_similar(
            query_embedding=question_embedding, top_k=max_context_docs
        )

        if not relevant_docs:
            return {
                "documents": [],
                "formatted_response": {
                    "response": (
                        "No relevant information found in the Bitcoin knowledge base."
                    ),
                    "sources": [],
                    "summary": "",
                },
                "message": (
                    "No relevant information found in the Bitcoin knowledge base."
                ),
            }

        # Format results with URL metadata support
        try:
            # Normalise to a uniform envelope so downstream access is consistent
            _out = QueryResultFormatter.format_structured_response(
                results=relevant_docs,
                query=query_text,
                include_summary=True,
            )
            formatted_response = {
                "formatted_response": _out,
                "sources": _out.get("sources", []),
                "summary": _out.get("summary", ""),
            }
        except Exception as e:
            # Log the formatting error but continue with fallback response
            logging.error(f"Error formatting query results: {str(e)}", exc_info=True)

            # Provide fallback formatted response
            formatted_response = {
                "formatted_response": {
                    "response": (
                        f"Found {len(relevant_docs)} relevant documents, but formatting failed."
                    ),
                    "sources": [
                        doc.get("metadata", {}).get("url", "Unknown source")
                        for doc in relevant_docs
                    ],
                    "summary": (
                        f"Retrieved {len(relevant_docs)} documents from Bitcoin knowledge base."
                    ),
                },
                "sources": [
                    doc.get("metadata", {}).get("url", "Unknown source")
                    for doc in relevant_docs
                ],
                "summary": (
                    f"Retrieved {len(relevant_docs)} documents from Bitcoin knowledge base."
                ),
            }

        return {
            "documents": relevant_docs,
            "formatted_response": formatted_response.get("formatted_response", {}),
            "sources": formatted_response.get("sources", []),
            "summary": formatted_response.get("summary", ""),
            "message": f"Found {len(relevant_docs)} relevant documents",
        }

    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        return self.pinecone_client.get_index_stats()
