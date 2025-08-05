#!/usr/bin/env python3
"""
Bitcoin Knowledge Assistant API using FastAPI and Pinecone Assistant
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, Header, HTTPException, Request, Response
from pinecone import Pinecone
from pinecone_plugins.assistant.models.chat import Message
from pydantic import BaseModel, Field

from utils.audio_utils import (create_gradio_streaming_audio,
                               extract_tts_content,
                               get_audio_streaming_manager,
                               prepare_audio_for_gradio)

# Import TTS components
try:
    from ..utils.tts_service import TTSError, get_tts_service
except ImportError:
    # Mock TTS components for testing purposes
    class TTSError(Exception):
        pass

    def get_tts_service():
        return None


from .admin_router import admin_router
from .rate_limiter import get_session_rate_limiter
# Import session management
from .session_manager import SessionData, get_session_manager

load_dotenv()

logger = logging.getLogger(__name__)

# Constants
SESSION_COOKIE_NAME = "btc_assistant_session"

app = FastAPI(
    title="Bitcoin Knowledge Assistant",
    description="AI-powered Bitcoin and blockchain knowledge assistant using Pinecone with TTS support",
    version="1.0.0",
)

# Include admin router with authentication
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on application startup"""
    try:
        from .admin_auth import get_admin_authenticator

        # Start admin session cleanup background task
        admin_auth = get_admin_authenticator()
        admin_auth.start_background_cleanup()
        logger.info("Application startup completed - background tasks initialized")
    except Exception as e:
        logger.error(f"Failed to initialize admin background tasks: {e}")
        # Don't raise - allow app to start even if admin tasks fail


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up background tasks on application shutdown"""
    try:
        from .admin_auth import get_admin_authenticator

        # Stop admin session cleanup background task
        admin_auth = get_admin_authenticator()
        admin_auth.stop_background_cleanup()
        logger.info("Application shutdown completed - background tasks stopped")
    except Exception as e:
        logger.error(f"Failed to stop admin background tasks: {e}")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    enable_tts: bool = False
    volume: float = Field(default=0.7, ge=0.0, le=1.0)


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict]
    raw_context: Optional[Dict] = None
    audio_data: Optional[str] = None
    audio_streaming_data: Optional[Dict] = None
    tts_enabled: bool = False
    tts_cached: bool = False
    session_id: Optional[str] = None
    conversation_turn: Optional[int] = None


class BitcoinAssistantService:
    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.assistant_name = "genius"  # From your screenshot

        if not self.api_key:
            raise ValueError("Missing PINECONE_API_KEY")

        # Initialize Pinecone client with assistant plugin
        self.pc = Pinecone(api_key=self.api_key)
        self.assistant = self.pc.assistant.Assistant(assistant_name=self.assistant_name)

        # Initialize session manager
        self.session_manager = get_session_manager()

        # Initialize TTS service and streaming manager
        try:
            self.tts_service = get_tts_service()
            self.streaming_manager = get_audio_streaming_manager()
        except Exception as e:
            logger.warning(f"Failed to initialize TTS services: {e}")
            self.tts_service = None
            self.streaming_manager = None

    def get_assistant_response(
        self, question: str, session_data: SessionData = None
    ) -> Dict:
        """Get intelligent response from Pinecone Assistant with session context"""
        try:
            # Build conversation context from session history
            messages = []

            if session_data:
                # Add recent conversation context for continuity
                context = session_data.get_conversation_context(max_turns=3)
                for turn in context:
                    messages.append(Message(role="user", content=turn["question"]))
                    messages.append(Message(role="assistant", content=turn["answer"]))

            # Add current question
            messages.append(Message(role="user", content=question))

            # Get response from Pinecone Assistant with conversation context
            response = self.assistant.chat(messages=messages)

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

    async def synthesize_response_audio(
        self, response_text: str, volume: float = 0.7
    ) -> Optional[Dict[str, any]]:
        """
        Synthesize audio for response text using TTS service with streaming support.

        Args:
            response_text: The formatted response text
            volume: Audio volume level (0.0 to 1.0)

        Returns:
            Dictionary with audio data, streaming data, and metadata, or None if TTS fails
        """
        if not self.tts_service.is_enabled():
            logger.warning("TTS service is not enabled")
            return None

        try:
            # Extract clean content for TTS (filter out sources and metadata)
            clean_content = extract_tts_content(response_text)

            if not clean_content.strip():
                logger.warning("No content available for TTS synthesis")
                return None

            # Check if audio is cached (instant replay)
            cached_audio = self.tts_service.get_cached_audio(clean_content)
            if cached_audio:
                logger.info("Using cached audio for instant replay")

                # Prepare streaming data for cached audio
                streaming_data = self.streaming_manager.create_instant_replay_data(
                    cached_audio
                )

                # Convert to Gradio format for backward compatibility
                audio_data = prepare_audio_for_gradio(cached_audio)

                return {
                    "audio_data": audio_data,
                    "streaming_data": streaming_data,
                    "cached": True,
                    "instant_replay": True,
                    "content_length": len(clean_content),
                    "synthesis_time": 0.0,
                }

            # Synthesize new audio
            synthesis_start = asyncio.get_event_loop().time()
            logger.info(f"Synthesizing audio for {len(clean_content)} characters")

            audio_bytes = await self.tts_service.synthesize_text(
                clean_content, volume=volume
            )
            synthesis_time = asyncio.get_event_loop().time() - synthesis_start

            # Prepare streaming data for new synthesis
            streaming_data = self.streaming_manager.create_synthesized_audio_data(
                audio_bytes, synthesis_time
            )

            # Convert to Gradio format for backward compatibility
            audio_data = prepare_audio_for_gradio(audio_bytes)

            return {
                "audio_data": audio_data,
                "streaming_data": streaming_data,
                "cached": False,
                "instant_replay": False,
                "content_length": len(clean_content),
                "synthesis_time": synthesis_time,
            }

        except TTSError as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during TTS synthesis: {e}")
            return None


# Initialize Bitcoin Assistant Service at module level
try:
    bitcoin_service = BitcoinAssistantService()
    logger.info("Bitcoin Assistant Service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Bitcoin Assistant Service: {e}")
    bitcoin_service = None


@app.get("/")
async def root():
    return {
        "message": "Bitcoin Knowledge Assistant API",
        "status": "running",
        "endpoints": [
            "/query",
            "/health",
            "/sources",
            "/session/new",
            "/session/{session_id}",
            "/tts/status",
            "/tts/clear-cache",
            "/tts/streaming/status",
            "/tts/streaming/test",
            "/docs",
        ],
        "admin_endpoints": [
            "/admin/login",
            "/admin/logout",
            "/admin/session/info",
            "/admin/sessions/stats",
            "/admin/sessions/cleanup",
            "/admin/sessions/rate-limits",
            "/admin/sessions/list",
            "/admin/sessions/{session_id}",
            "/admin/auth/stats",
            "/admin/health",
        ],
        "features": {
            "session_management": "Conversation isolation with unique session IDs",
            "conversation_context": "Maintains conversation history within sessions",
            "automatic_cleanup": "Expired sessions cleaned up automatically",
            "admin_authentication": "Secure admin access with token-based authentication",
            "rate_limiting": "Anti-enumeration protection with per-endpoint limits",
            "security_logging": "Comprehensive logging of all access attempts",
            "text_to_speech": "Available with ElevenLabs integration",
            "audio_caching": "In-memory LRU cache for generated audio",
            "audio_streaming": "Real-time audio streaming with instant replay for cached content",
            "content_filtering": "Automatic source removal for clean TTS",
            "instant_replay": "Cached audio plays instantly without re-synthesis",
        },
    }


@app.post("/session/new")
async def create_new_session(request: Request, response: Response):
    """Create a new session with rate limiting"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit
    rate_limiter = get_session_rate_limiter()
    if not rate_limiter.check_session_create_limit(client_ip):
        logger.warning(f"Session creation rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many session creation requests. Please try again later.",
        )

    try:
        session_id = bitcoin_service.session_manager.create_session()

        # Set session cookie
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            max_age=3600,  # 1 hour
            httponly=True,
            samesite="lax",
        )

        logger.info(f"New session created for IP {client_ip}: {session_id[:8]}...")

        return {
            "session_id": session_id,
            "message": "New session created",
            "expires_in_minutes": 60,
        }
    except Exception as e:
        logger.error(f"Failed to create session for IP {client_ip}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create session: {str(e)}"
        )


@app.get("/session/{session_id}")
async def get_session_info(
    session_id: str,
    request: Request,
    btc_assistant_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Get session information and conversation history with authentication and rate limiting"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Get client IP for rate limiting and logging
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit to prevent session enumeration attacks
    rate_limiter = get_session_rate_limiter()
    if not rate_limiter.check_session_info_limit(client_ip):
        logger.warning(
            f"Session info rate limit exceeded for IP: {client_ip}, session: {session_id[:8]}..."
        )
        raise HTTPException(
            status_code=429,
            detail="Too many session info requests. Please try again later.",
        )

    try:
        # Validate session ownership - user can only access their own session info
        current_session_id = btc_assistant_session

        if not current_session_id:
            logger.warning(
                f"Unauthorized session access attempt from IP {client_ip} for session {session_id[:8]}..."
            )
            raise HTTPException(
                status_code=401,
                detail="No active session found. Session access requires an active session cookie.",
            )

        if current_session_id != session_id:
            logger.warning(
                f"Session ownership violation from IP {client_ip}: attempted access to {session_id[:8]}... with cookie {current_session_id[:8]}..."
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You can only access your own session information. Session ownership validation failed.",
            )

        session_data = bitcoin_service.session_manager.get_session(session_id)
        if not session_data:
            logger.info(
                f"Session not found or expired: {session_id[:8]}... from IP {client_ip}"
            )
            raise HTTPException(status_code=404, detail="Session not found or expired")

        logger.info(
            f"Session info accessed successfully: {session_id[:8]}... from IP {client_ip}"
        )

        return {
            "session_info": session_data.to_dict(),
            "conversation_history": session_data.conversation_history,
            "conversation_context": session_data.get_conversation_context(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get session info for {session_id[:8]}... from IP {client_ip}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get session info: {str(e)}"
        )


@app.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
    response: Response,
    btc_assistant_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Delete a specific session with authentication, ownership validation, and rate limiting"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Get client IP for rate limiting and logging
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit to prevent abuse
    rate_limiter = get_session_rate_limiter()
    if not rate_limiter.check_session_delete_limit(client_ip):
        logger.warning(
            f"Session deletion rate limit exceeded for IP: {client_ip}, session: {session_id[:8]}..."
        )
        raise HTTPException(
            status_code=429,
            detail="Too many session deletion requests. Please try again later.",
        )

    try:
        # Validate session ownership - user can only delete their own session
        current_session_id = btc_assistant_session

        if not current_session_id:
            logger.warning(
                f"Unauthorized session deletion attempt from IP {client_ip} for session {session_id[:8]}..."
            )
            raise HTTPException(
                status_code=401,
                detail="No active session found. Session deletion requires an active session cookie.",
            )

        if current_session_id != session_id:
            logger.warning(
                f"Session deletion ownership violation from IP {client_ip}: attempted deletion of {session_id[:8]}... with cookie {current_session_id[:8]}..."
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You can only delete your own session. Session ownership validation failed.",
            )

        # Verify the session exists before attempting deletion
        session_data = bitcoin_service.session_manager.get_session(session_id)
        if not session_data:
            logger.info(
                f"Session deletion attempted for non-existent session: {session_id[:8]}... from IP {client_ip}"
            )
            raise HTTPException(
                status_code=404, detail="Session not found or already expired"
            )

        # Proceed with deletion since ownership is validated
        removed = bitcoin_service.session_manager.remove_session(session_id)

        # Clear session cookie
        response.delete_cookie(key=SESSION_COOKIE_NAME)

        if removed:
            logger.info(
                f"Session deleted successfully: {session_id[:8]}... from IP {client_ip}"
            )
            return {
                "message": "Session deleted successfully",
                "session_id": session_id,
                "deleted_at": time.time(),
            }
        else:
            # This shouldn't happen since we verified existence above, but handle gracefully
            logger.error(
                f"Session deletion failed unexpectedly: {session_id[:8]}... from IP {client_ip}"
            )
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete session {session_id[:8]}... from IP {client_ip}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete session: {str(e)}"
        )


# Admin endpoints moved to separate admin router for security


@app.get("/health")
async def health_check():
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Test Pinecone Assistant connection with a simple query (run in thread to avoid blocking)
        test_response = await asyncio.to_thread(
            bitcoin_service.get_assistant_response, "What is Bitcoin?"
        )

        # Check TTS service status
        tts_status = "disabled"
        tts_api_key_configured = False
        if bitcoin_service.tts_service:
            tts_status = (
                "enabled" if bitcoin_service.tts_service.is_enabled() else "disabled"
            )
            tts_api_key_configured = bool(bitcoin_service.tts_service.config.api_key)
        return {
            "status": "healthy",
            "pinecone_assistant": "connected",
            "assistant_name": bitcoin_service.assistant_name,
            "test_response_received": bool(test_response.get("answer")),
            "tts_service": tts_status,
            "tts_api_key_configured": tts_api_key_configured,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")


@app.post("/query", response_model=QueryResponse)
async def query_bitcoin_knowledge(request: QueryRequest, response: Response):
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Get or create session
        session_id, session_data = (
            bitcoin_service.session_manager.get_or_create_session(request.session_id)
        )

        # Set session cookie for browser persistence
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            max_age=3600,  # 1 hour
            httponly=True,
            samesite="lax",
        )

        # Get response from Pinecone Assistant with session context (run in thread to avoid blocking)
        response_data = await asyncio.to_thread(
            bitcoin_service.get_assistant_response, request.question, session_data
        )

        # Format the assistant response
        answer = bitcoin_service.format_assistant_response(response_data)

        # Extract sources from the response
        sources = response_data.get("sources", [])

        # Add conversation turn to session history
        session_data.add_conversation_turn(request.question, answer, sources)

        # Initialize response data
        audio_data = None
        audio_streaming_data = None
        tts_cached = False
        tts_synthesis_time = None

        # Process TTS if enabled
        if request.enable_tts and bitcoin_service.tts_service:
            try:
                tts_result = await bitcoin_service.synthesize_response_audio(
                    answer, request.volume
                )
                if tts_result:
                    audio_data = tts_result["audio_data"]
                    audio_streaming_data = tts_result.get("streaming_data")
                    tts_cached = tts_result["cached"]
                    tts_synthesis_time = tts_result.get("synthesis_time")
            except Exception as e:
                # Log TTS error but don't fail the entire request
                logger.warning(
                    f"TTS synthesis failed, continuing with text-only response: {e}"
                )
                # TTS variables remain None, indicating fallback to muted state

        return QueryResponse(
            answer=answer,
            sources=sources,
            raw_context=None,  # Raw context removed for cleaner responses
            audio_data=audio_data,
            audio_streaming_data=audio_streaming_data,
            tts_enabled=request.enable_tts and bitcoin_service.tts_service.is_enabled(),
            tts_synthesis_time=tts_synthesis_time,
            session_id=session_id,
            conversation_turn=len(session_data.conversation_history),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/sources")
async def list_available_sources():
    """List available sources in the knowledge base"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Get a broad context to see available sources (run in thread to avoid blocking)
        context = await asyncio.to_thread(
            bitcoin_service.get_assistant_response, "Bitcoin blockchain cryptocurrency"
        )

        sources = {s.get("name") for s in context.get("sources", []) if s.get("name")}
        return {
            "available_sources": sorted(list(sources)),
            "total_sources": len(sources),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sources: {str(e)}")


@app.get("/tts/status")
async def get_tts_status():
    """Get TTS service status and configuration with performance metrics"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not bitcoin_service.tts_service:
        return {
            "enabled": False,
            "api_key_configured": False,
            "error": "TTS service not initialized",
        }

    try:
        tts_service = bitcoin_service.tts_service
        cache_stats = tts_service.get_cache_stats()
        error_state = tts_service.get_error_state()
        performance_stats = tts_service.get_performance_stats()

        return {
            "enabled": tts_service.is_enabled(),
            "api_key_configured": bool(tts_service.config.api_key),
            "voice_id": tts_service.config.voice_id,
            "model_id": tts_service.config.model_id,
            "cache_stats": cache_stats,
            "error_state": error_state,
            "performance": performance_stats,
            "config": {
                "cache_size": tts_service.config.cache_size,
                "output_format": tts_service.config.output_format,
                "volume": tts_service.config.volume,
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get TTS status: {str(e)}"
        )


@app.post("/tts/recovery")
async def attempt_tts_recovery():
    """Attempt to recover TTS service from error state"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not bitcoin_service.tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    try:
        recovery_successful = await bitcoin_service.tts_service.attempt_recovery()
        error_state = bitcoin_service.tts_service.get_error_state()

        return {
            "recovery_attempted": True,
            "recovery_successful": recovery_successful,
            "current_error_state": error_state,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Recovery attempt failed: {str(e)}"
        )


@app.post("/tts/clear-cache")
async def clear_tts_cache():
    """Clear TTS audio cache"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not bitcoin_service.tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    try:
        bitcoin_service.tts_service.clear_cache()
        return {"message": "TTS cache cleared successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to clear TTS cache: {str(e)}"
        )


@app.post("/tts/optimize")
async def optimize_tts_performance():
    """Optimize TTS service performance"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not bitcoin_service.tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    try:
        optimization_results = bitcoin_service.tts_service.optimize_performance()

        # Also optimize streaming manager if available
        streaming_optimization = {}
        if bitcoin_service.streaming_manager:
            streaming_optimization = (
                bitcoin_service.streaming_manager.optimize_streaming_performance()
            )

        return {
            "message": "Performance optimization completed",
            "tts_optimization": optimization_results,
            "streaming_optimization": streaming_optimization,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Performance optimization failed: {str(e)}"
        )


@app.get("/tts/performance")
async def get_tts_performance_metrics():
    """Get detailed TTS performance metrics"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not bitcoin_service.tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    try:
        performance_stats = bitcoin_service.tts_service.get_performance_stats()
        streaming_status = {}

        if bitcoin_service.streaming_manager:
            streaming_status = bitcoin_service.streaming_manager.get_stream_status()

        return {
            "tts_performance": performance_stats,
            "streaming_status": streaming_status,
            "timestamp": time.time(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance metrics: {str(e)}"
        )


@app.get("/tts/streaming/status")
async def get_streaming_status():
    """Get audio streaming status"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not bitcoin_service.streaming_manager or not bitcoin_service.tts_service:
        return {
            "streaming_manager": None,
            "tts_enabled": False,
            "error": "TTS services not initialized",
        }

    try:
        streaming_status = bitcoin_service.streaming_manager.get_stream_status()
        return {
            "streaming_manager": streaming_status,
            "tts_enabled": bitcoin_service.tts_service.is_enabled(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get streaming status: {str(e)}"
        )


class StreamingTestRequest(BaseModel):
    text: str
    use_cache: Optional[bool] = True


@app.post("/tts/streaming/test")
async def test_streaming_audio(request: StreamingTestRequest):
    """Test audio streaming functionality"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not bitcoin_service.tts_service.is_enabled():
        raise HTTPException(status_code=503, detail="TTS service is not enabled")

    try:
        # Synthesize test audio
        tts_result = await bitcoin_service.synthesize_response_audio(request.text, 0.7)

        if not tts_result:
            raise HTTPException(
                status_code=500, detail="Failed to synthesize test audio"
            )

        streaming_data = tts_result.get("streaming_data")
        if not streaming_data:
            raise HTTPException(status_code=500, detail="No streaming data generated")

        return {
            "message": "Streaming test successful",
            "streaming_data": {
                "duration": streaming_data.get("duration"),
                "is_cached": streaming_data.get("is_cached"),
                "instant_replay": streaming_data.get("instant_replay"),
                "size_bytes": streaming_data.get("size_bytes"),
                "synthesis_time": streaming_data.get("synthesis_time"),
            },
            "audio_available": bool(tts_result.get("audio_data")),
            "cached": tts_result.get("cached", False),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming test failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    # Configure logging only when running as main program
    logging.basicConfig(level=logging.INFO)

    uvicorn.run(app, host="0.0.0.0", port=8000)
