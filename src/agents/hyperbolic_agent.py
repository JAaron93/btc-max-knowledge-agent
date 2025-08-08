from typing import Any, Dict, List

from btc_max_knowledge_agent.retrieval.hyperbolic_client import HyperbolicClient


class HyperbolicKnowledgeAgent:
    """Minimal agent wrapper using Hyperbolic GPT-OSS 120B.

    Mirrors the BitcoinKnowledgeAgent interface for easy toggling.
    """

    def __init__(self) -> None:
        self.client = HyperbolicClient()

    async def answer_question(
        self,
        question_embedding: List[float],  # Unused in minimal demo
        max_context_docs: int = 5,  # Unused in minimal demo
        query_text: str = "",
    ) -> Dict[str, Any]:
        gen = await self.client.generate(
            query_text or "Provide information about Bitcoin."
        )
        return {
            "documents": [],
            "formatted_response": {
                "response": gen.get("response", ""),
                "sources": [],
                "summary": "",
            },
            "sources": [],
            "summary": "",
            "message": "Generated response from Hyperbolic GPT-OSS 120B",
            "model": gen.get("model"),
            "usage": gen.get("usage", {}),
        }


