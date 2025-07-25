#!/usr/bin/env python3
"""
Bitcoin Knowledge Assistant API using FastAPI and Pinecone Assistant
"""

import asyncio
import os
import logging
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pinecone import Pinecone
from pinecone_plugins.assistant.models.chat import Message
from pydantic import BaseModel

# Import TTS components
from ..utils.tts_service import get_tts_service, TTSError
from utils.tts_service import get_tts_service, TTSError
from utils.audio_utils import (
    extract_tts_content, 
    prepare_audio_for_gradio, 
    get_audio_streaming_manager,
    create_gradio_streaming_audio
)

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bitcoin Knowledge Assistant",
    description="AI-powered Bitcoin and blockchain knowledge assistant using Pinecone with TTS support",
    version="1.0.0",
)


class QueryRequest(BaseModel):
    question: str
    enable_tts: Optional[bool] = False


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict]
    raw_context: Optional[Dict] = None
    audio_data: Optional[str] = None
    audio_streaming_data: Optional[Dict] = None
    tts_enabled: bool = False
    tts_cached: bool = False
    tts_synthesis_time: Optional[float] = None


class BitcoinAssistantService:
    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.assistant_name = "genius"  # From your screenshot

        if not self.api_key:
            raise ValueError("Missing PINECONE_API_KEY")

        # Initialize Pinecone client with assistant plugin
        self.pc = Pinecone(api_key=self.api_key)
        self.assistant = self.pc.assistant.Assistant(assistant_name=self.assistant_name)
        # Initialize TTS service and streaming manager
        try:
            self.tts_service = get_tts_service()
            self.streaming_manager = get_audio_streaming_manager()
        except Exception as e:
            logger.warning(f"Failed to initialize TTS services: {e}")
            self.tts_service = None
            self.streaming_manager = None
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

    async def synthesize_response_audio(self, response_text: str) -> Optional[Dict[str, any]]:
        """
        Synthesize audio for response text using TTS service with streaming support.
        
        Args:
            response_text: The formatted response text
            
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
                streaming_data = self.streaming_manager.create_instant_replay_data(cached_audio)
                
                # Convert to Gradio format for backward compatibility
                audio_data = prepare_audio_for_gradio(cached_audio)
                
                return {
                    "audio_data": audio_data,
                    "streaming_data": streaming_data,
                    "cached": True,
                    "instant_replay": True,
                    "content_length": len(clean_content),
                    "synthesis_time": 0.0
                }
            
            # Synthesize new audio
            synthesis_start = asyncio.get_event_loop().time()
            logger.info(f"Synthesizing audio for {len(clean_content)} characters")
            
            audio_bytes = await self.tts_service.synthesize_text(clean_content)
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
                "synthesis_time": synthesis_time
            }
            
        except TTSError as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during TTS synthesis: {e}")
            return None
    print(f"Failed to initialize Bitcoin Assistant Service: {e}")
    bitcoin_service = None


@app.get("/")
async def root():
    return {
        "message": "Bitcoin Knowledge Assistant API",
        "status": "running",
        "endpoints": [
            "/query", "/health", "/sources", 
            "/tts/status", "/tts/clear-cache", "/tts/streaming/status", "/tts/streaming/test",
            "/docs"
        ],
        "features": {
            "text_to_speech": "Available with ElevenLabs integration",
            "audio_caching": "In-memory LRU cache for generated audio",
            "audio_streaming": "Real-time audio streaming with instant replay for cached content",
            "content_filtering": "Automatic source removal for clean TTS",
            "instant_replay": "Cached audio plays instantly without re-synthesis"
        }
    }


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
            tts_status = "enabled" if bitcoin_service.tts_service.is_enabled() else "disabled"
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
async def query_bitcoin_knowledge(request: QueryRequest):
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Get response from Pinecone Assistant (run in thread to avoid blocking)
        response_data = await asyncio.to_thread(
            bitcoin_service.get_assistant_response, request.question
        )

        # Format the assistant response
        answer = bitcoin_service.format_assistant_response(response_data)

        # Extract sources from the response
        sources = response_data.get("sources", [])

        # Initialize response data
        audio_data = None
        audio_streaming_data = None
        tts_cached = False
        tts_synthesis_time = None
        
        # Process TTS if enabled
        if request.enable_tts and bitcoin_service.tts_service:
            try:
                tts_result = await bitcoin_service.synthesize_response_audio(answer)
                if tts_result:
                    audio_data = tts_result["audio_data"]
                    audio_streaming_data = tts_result.get("streaming_data")
                    tts_cached = tts_result["cached"]
                    tts_synthesis_time = tts_result.get("synthesis_time")
            except Exception as e:
                # Log TTS error but don't fail the entire request
                logger.warning(f"TTS synthesis failed, continuing with text-only response: {e}")
                # TTS variables remain None, indicating fallback to muted state
        return QueryResponse(
            answer=answer,
            sources=sources,
            raw_context=None,  # Raw context removed for cleaner responses
            audio_data=audio_data,
            audio_streaming_data=audio_streaming_data,
            tts_enabled=request.enable_tts and bitcoin_service.tts_service.is_enabled(),
            tts_enabled=request.enable_tts 
                and bitcoin_service.tts_service 
                and bitcoin_service.tts_service.is_enabled(),
            tts_synthesis_time=tts_synthesis_time
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
            bitcoin_service.get_assistant_response,
            "Bitcoin blockchain cryptocurrency"
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
    """Get TTS service status and configuration"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not bitcoin_service.tts_service:
        return {
            "enabled": False,
            "api_key_configured": False,
            "error": "TTS service not initialized"
        }

    try:
        tts_service = bitcoin_service.tts_service
        cache_stats = tts_service.get_cache_stats()
        error_state = tts_service.get_error_state()
        
        return {
            "enabled": tts_service.is_enabled(),
            "api_key_configured": bool(tts_service.config.api_key),
            "voice_id": tts_service.config.voice_id,
            "model_id": tts_service.config.model_id,
            "cache_stats": cache_stats,
            "error_state": error_state,
            "config": {
                "cache_size": tts_service.config.cache_size,
                "output_format": tts_service.config.output_format,
                "volume": tts_service.config.volume
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get TTS status: {str(e)}")


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
            "current_error_state": error_state
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recovery attempt failed: {str(e)}")
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
        raise HTTPException(status_code=500, detail=f"Failed to clear TTS cache: {str(e)}")

    try:
        bitcoin_service.tts_service.clear_cache()
        return {"message": "TTS cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear TTS cache: {str(e)}")

@app.get("/tts/streaming/status")
async def get_streaming_status():
    """Get audio streaming status"""
    if not bitcoin_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not bitcoin_service.streaming_manager or not bitcoin_service.tts_service:
        return {
            "streaming_manager": None,
            "tts_enabled": False,
            "error": "TTS services not initialized"
        }

    try:
        streaming_status = bitcoin_service.streaming_manager.get_stream_status()
        return {
            "streaming_manager": streaming_status,
            "tts_enabled": bitcoin_service.tts_service.is_enabled()
        }
    if not bitcoin_service.tts_service or not bitcoin_service.tts_service.is_enabled():
        raise HTTPException(status_code=503, detail="TTS service is not enabled")


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
        tts_result = await bitcoin_service.synthesize_response_audio(request.text)
        
        if not tts_result:
            raise HTTPException(status_code=500, detail="Failed to synthesize test audio")
        
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
                "synthesis_time": streaming_data.get("synthesis_time")
            },
            "audio_available": bool(tts_result.get("audio_data")),
            "cached": tts_result.get("cached", False)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming test failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    # Configure logging only when running as main program
    logging.basicConfig(level=logging.INFO)

    uvicorn.run(app, host="0.0.0.0", port=8000)
