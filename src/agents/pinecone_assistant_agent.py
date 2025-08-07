from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional


# Type alias for DI: matches secure_preprocess(text, context) signature
SecurityProcessor = Callable[[str, Optional[Dict[str, Any]]], Awaitable[Any]]


@dataclass
class PineconeAssistantAgent:
    api_key: Optional[str] = None
    index: Optional[str] = None
    # Inject security processor to avoid lazy import and improve testability.
    # Defaults to None; if not provided, a safe lazy initializer is used once.
    security_processor: Optional[SecurityProcessor] = field(default=None, repr=False)

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
        Process user text with secure_preprocess before any model/RAG
        operations. Returns a minimal stubbed response and short-circuits on
        BLOCK. For SANITIZE/CONSTRAIN, the sanitized text is used and a
        non-leaky policy marker is included in metadata.
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
        is_block = (
            (not sp_result.allowed)
            or (
                getattr(sp_result, "action_taken", None)
                and sp_result.action_taken.name == "BLOCK"
            )
        )
        if is_block:
            raise RuntimeError(
                "Request content blocked due to security policy."
            )

        # SANITIZE or CONSTRAIN: use sanitized_text if present; otherwise original
        if getattr(sp_result, "action_taken", None) and (
            sp_result.action_taken.name in {"SANITIZE", "CONSTRAIN"}
        ):
            processed_text = sp_result.sanitized_text or text
        else:
            processed_text = text

        # Existing behavior was a stubbed search result; preserve shape
        result: List[Dict[str, Any]] = [
            {"text": processed_text, "score": 1.0, "id": "stub"}
        ]

        # If CONSTRAIN, add a minimal indicator for downstream policy handling
        if getattr(sp_result, "action_taken", None) and (
            sp_result.action_taken.name == "CONSTRAIN"
        ):
            result[0]["policy_applied"] = True
            # Do NOT include raw wrapper text in user-facing paths.

        return result

    def upsert(self, items: List[Dict[str, Any]]) -> int:
        return len(items)
