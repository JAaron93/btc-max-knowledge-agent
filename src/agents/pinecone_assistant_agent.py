from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional
import logging
import google.generativeai as genai
import os

logger = logging.getLogger(__name__)

# Type alias for DI: matches secure_preprocess(text, context) signature
SecurityProcessor = Callable[[str, Optional[Dict[str, Any]]], Awaitable[Any]]


@dataclass
class PineconeAssistantAgent:
    api_key: Optional[str] = None
    index: Optional[str] = None
    # Inject security processor to avoid lazy import and improve testability.
    # Defaults to None; if not provided, a safe lazy initializer is used once.
    security_processor: Optional[SecurityProcessor] = field(default=None, repr=False)
    _pinecone_client: Optional[Any] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize Gemini API for embeddings"""
        # Configure Gemini API
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            genai.configure(api_key=google_api_key)
        else:
            logger.warning("GOOGLE_API_KEY not found, embeddings may fail")

    def _get_pinecone_client(self):
        """Lazy initialization of PineconeClient"""
        if self._pinecone_client is None:
            try:
                from src.retrieval.pinecone_client import PineconeClient

                self._pinecone_client = PineconeClient()
                logger.info("✅ PineconeClient initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize PineconeClient: {e}")
                self._pinecone_client = None
        return self._pinecone_client

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Gemini text-embedding-004 model"""
        try:
            # Use Gemini's text-embedding-004 model
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_query",
            )
            return result["embedding"]
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * 768  # text-embedding-004 dimension

    def _truncate_at_word_boundary(self, text: str, max_length: int = 500) -> str:
        """
        Truncate text at the nearest word boundary before the limit.
        Appends ellipsis if truncated.

        Args:
            text: The text to truncate
            max_length: Maximum character length (default: 500)

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_length:
            return text

        # Find the last space before the limit
        truncated = text[:max_length]
        last_space = truncated.rfind(" ")

        # If no space found, truncate at the limit (edge case for very long words)
        if last_space == -1:
            return text[:max_length] + "..."

        # Truncate at the last word boundary and add ellipsis
        return text[:last_space] + "..."

    async def _get_security_processor(self) -> SecurityProcessor:
        """
        Lazy initializer for security processor only if not injected.
        This maintains backward compatibility while enabling DI for tests.
        """
        if self.security_processor is not None:
            return self.security_processor
        # Deferred import to avoid cycles only when DI not used.
        # mypy: The security module exposes a runtime-available callable but may not ship
        # stub files in some environments, causing a false-positive import error.
        # We intentionally ignore type checking here to keep DI-friendly lazy import,
        # avoiding tight coupling while preserving runtime safety via call signature.
        from src.security.prompt_processor import (  # type: ignore[import]
            secure_preprocess as secure_preprocess_prompt,
        )

        # Cache for subsequent calls
        self.security_processor = secure_preprocess_prompt
        return secure_preprocess_prompt

    async def query(  # type: ignore[override]
        self,
        text: str,
        top_k: int = 5,
        *,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process user text with secure_preprocess and then perform RAG query
        against the Pinecone vector database with 224 Bitcoin/crypto document chunks.
        """
        sec_proc = await self._get_security_processor()

        context: Dict[str, Any] = {}
        if session_id:
            context["session_id"] = session_id
        if request_id:
            context["request_id"] = request_id
        if source_ip:
            context["source_ip"] = source_ip
        if user_agent:
            context["user_agent"] = user_agent

        sp_result = await sec_proc(text, context=context)

        # BLOCK: refuse without leaking detection details
        is_block = (not sp_result.allowed) or (
            getattr(sp_result, "action_taken", None)
            and sp_result.action_taken.name == "BLOCK"
        )
        if is_block:
            raise RuntimeError("Request content blocked due to security policy.")

        # SANITIZE or CONSTRAIN: use sanitized_text if present; otherwise original
        if getattr(sp_result, "action_taken", None) and (
            sp_result.action_taken.name in {"SANITIZE", "CONSTRAIN"}
        ):
            processed_text = sp_result.sanitized_text or text
        else:
            processed_text = text

        # Now perform actual RAG query using PineconeClient
        pinecone_client = self._get_pinecone_client()

        if pinecone_client is None:
            logger.warning("PineconeClient not available, returning stub response")
            result: List[Dict[str, Any]] = [
                {"text": processed_text, "score": 1.0, "id": "stub"}
            ]
        else:
            try:
                # Generate embedding for the query
                logger.info(
                    f"🔍 Generating embedding for query: '{processed_text[:50]}...'"
                )
                query_embedding = self._generate_embedding(processed_text)

                # Query the vector database
                logger.info(f"🔎 Querying Pinecone with top_k={top_k}")
                search_results = pinecone_client.query_similar(
                    query_embedding, top_k=top_k
                )

                # Format results for the API response
                result = []
                for i, doc in enumerate(search_results):
                    formatted_result = {
                        "text": self._truncate_at_word_boundary(doc.get("content", "")),
                        "score": float(doc.get("score", 0.0)),
                        "id": doc.get("id", f"doc_{i}"),
                        "title": doc.get("title", ""),
                        "source": doc.get("source", ""),
                        "url": doc.get("url", ""),
                    }
                    result.append(formatted_result)

                logger.info(
                    f"✅ Retrieved {len(result)} relevant documents from vector database"
                )

            except Exception as e:
                logger.error(f"❌ Error querying Pinecone: {e}")
                # Fallback to stub response
                result = [
                    {
                        "text": f"Error retrieving results: {str(e)}",
                        "score": 0.0,
                        "id": "error",
                    }
                ]

        # If CONSTRAIN, add a minimal indicator for downstream policy handling
        if getattr(sp_result, "action_taken", None) and (
            sp_result.action_taken.name == "CONSTRAIN"
        ):
            for item in result:
                item["policy_applied"] = True
            # Do NOT include raw wrapper text in user-facing paths.

        return result

    def upsert(self, items: List[Dict[str, Any]]) -> int:
        return len(items)
