try:
    from fastapi import FastAPI
    from fastapi import Request, Body, APIRouter
    from fastapi.responses import JSONResponse
except Exception:
    # Minimal stubs if FastAPI not installed
    class FastAPI:  # type: ignore
        def __init__(self):
            self.routes = []

    class Request:  # type: ignore
        def __init__(self):
            self.state = type("S", (), {})()
            self.client = type("C", (), {"host": "unknown"})()
            self.headers = {}

    def Body(default):  # type: ignore
        """
        Stub for fastapi.Body used as a dependency injection marker.
        Note: This is not a functional replacement for FastAPI's Body.
        It must not be executed when FastAPI is unavailable.
        """
        raise RuntimeError(
            "fastapi.Body stub invoked. This is a DI marker only and must not "
            "be called outside FastAPI. Install FastAPI to use Body correctly."
        )

    class JSONResponse(dict):  # type: ignore
        def __init__(self, content, status_code=200):
            super().__init__(content)
            self.status_code = status_code

    class APIRouter:  # type: ignore
        def __init__(self):
            self.routes = []

        def post(self, path: str):
            def decorator(func):
                self.routes.append((path, func))
                return func

            return decorator


from typing import Any, Dict, Optional

# Lazy agent import to avoid cycles at module import
try:
    from src.agents.pinecone_assistant_agent import PineconeAssistantAgent
except Exception:
    PineconeAssistantAgent = None  # type: ignore

from src.security.prompt_processor import (
    secure_preprocess as secure_preprocess_prompt,  # type: ignore
)


app = FastAPI()
router = APIRouter()  # type: ignore


# Lazy, cached agent instance to avoid per-request construction overhead.
_AGENT_INSTANCE = None  # type: ignore


def _get_agent():
    """
    Return a cached PineconeAssistantAgent instance if available.
    Lazily instantiate on first use to avoid import-time costs and
    keep compatibility with the existing lazy import logic.
    """
    global _AGENT_INSTANCE
    if _AGENT_INSTANCE is None:
        if PineconeAssistantAgent is None:
            return None
        _AGENT_INSTANCE = PineconeAssistantAgent()
    return _AGENT_INSTANCE


def _get_request_id(req: Request) -> Optional[str]:  # type: ignore
    rid = getattr(getattr(req, "state", object()), "request_id", None)
    if isinstance(rid, str):
        return rid
    return None


# Define a minimal payload shape without pydantic to keep import-light
# Clients send: {"text": "..."} and optionally {"top_k": 5}
# Router is always defined when APIRouter is importable or stubbed.
@router.post("/chat")  # type: ignore[misc]
async def chat_endpoint(  # type: ignore[no-redef]
    request: Request,  # type: ignore[name-defined]
    payload: Dict[str, Any] = Body(  # type: ignore[name-defined]
        default={}
    ),
):
    # Gather context safely, no raw prompt logging/returning
    request_id = _get_request_id(request)
    session_id = getattr(
        getattr(request, "state", object()),
        "session_id",
        None,
    )
    source_ip = getattr(getattr(request, "client", object()), "host", None)
    headers = getattr(request, "headers", {})
    user_agent = headers.get("user-agent") if hasattr(headers, "get") else None
    text: str = str(payload.get("text", "") or "")
    try:
        top_k: int = int(payload.get("top_k", 5))
    except (ValueError, TypeError):
        top_k: int = 5
    # Apply secure preprocessing before any agent/LLM/RAG
    sp_result = await secure_preprocess_prompt(
        text,
        context={
            **({"session_id": session_id} if session_id else {}),
            **({"request_id": request_id} if request_id else {}),
            **({"source_ip": source_ip} if source_ip else {}),
            **({"user_agent": user_agent} if user_agent else {}),
        },
    )

    # BLOCK: return safe 422 with request_id only
    is_block = (not sp_result.allowed) or (
        getattr(sp_result, "action_taken", None)
        and sp_result.action_taken.name == "BLOCK"
    )
    if is_block:
        return JSONResponse(
            {
                "error": ("Request content blocked due to security policy."),
                "request_id": request_id,
            },
            status_code=422,
        )

    # Determine processed text for SANITIZE / CONSTRAIN / ALLOW
    processed_text: str = text
    if getattr(sp_result, "action_taken", None):
        action_name = sp_result.action_taken.name
        if action_name in ("SANITIZE", "CONSTRAIN"):
            processed_text = sp_result.sanitized_text or text

    # Forward to agent; if CONSTRAIN, agent sets policy_applied flag
    # internally
    if PineconeAssistantAgent is None:
        return {"result": [{"text": processed_text, "score": 1.0, "id": "stub"}]}

    agent = _get_agent()
    if agent is None:
        return {"result": [{"text": processed_text, "score": 1.0, "id": "stub"}]}
    results = await agent.query(
        processed_text,
        top_k=top_k,
        session_id=session_id,
        request_id=request_id,
        source_ip=source_ip,
        user_agent=user_agent,
    )

    # Do not include system policy wrapper contents in response
    return {"result": results, "request_id": request_id}

# Mount router if FastAPI real
try:
    app.include_router(router)  # type: ignore[attr-defined]
except Exception as e:
    # Do not fail silently; log the exception to aid debugging in non-FastAPI environments
    try:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to include API router: %s", str(e)
        )
    except Exception:
        # Fallback to print if logging is unavailable
        print(f"[bitcoin_assistant_api] Failed to include API router: {e}")
