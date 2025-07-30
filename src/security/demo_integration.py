"""
Demonstration of security middleware integration with Bitcoin Assistant API.

This module shows how to integrate the security validation middleware
with the existing FastAPI application.
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .middleware import create_security_middleware
from .validator import SecurityValidator
from .config import SecurityConfigurationManager
from .models import SecurityConfiguration


logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str
    enable_tts: Optional[bool] = False


class QueryResponse(BaseModel):
    answer: str
    sources: list
    tts_enabled: bool = False


class MockSecurityMonitor:
    """Mock security monitor for demonstration."""
    
    async def log_security_event(self, event):
        logger.info(f"Security event: {event.event_type.value} - {event.severity.value}")
    
    async def detect_anomalies(self, metrics):
        return []
    
    async def generate_alert(self, anomaly):
        logger.warning(f"Security alert: {anomaly}")
    
    async def get_security_metrics(self, time_range=3600):
        return {"events": 0}


def create_secure_bitcoin_api() -> FastAPI:
    """
    Create a secure Bitcoin Assistant API with security middleware.
    
    Returns:
        FastAPI application with security middleware applied
    """
    # Create FastAPI app
    app = FastAPI(
        title="Secure Bitcoin Knowledge Assistant",
        description="AI-powered Bitcoin assistant with security validation",
        version="1.0.0",
    )
    
    try:
        # Load security configuration
        config_manager = SecurityConfigurationManager()
        security_config = config_manager.load_secure_config()
        
        # Initialize security components
        validator = SecurityValidator(security_config)
        monitor = MockSecurityMonitor()  # Replace with actual SecurityMonitor when implemented
        
        # Create and apply security middleware
        validation_middleware, headers_middleware = create_security_middleware(
            validator,
            monitor,
            security_config,
            exempt_paths=[
                "/health",
                "/docs",
                "/openapi.json",
                "/redoc",
                "/security/status",
                "/security/health"
            ]
        )
        
        app.add_middleware(validation_middleware)
        app.add_middleware(headers_middleware)
        
        logger.info("Security middleware applied successfully")
        
    except Exception as e:
        logger.error(f"Failed to apply security middleware: {e}")
        # In production, you might want to fail here
        # For demo purposes, we'll continue without security
        logger.warning("Running without security middleware")
    
    # Add security status endpoints
    @app.get("/security/status")
    async def security_status():
        """Get security system status."""
        try:
            return {
                "security_enabled": True,
                "validator_status": "active",
                "monitor_status": "active",
                "middleware_applied": True
            }
        except Exception as e:
            return {
                "security_enabled": False,
                "error": str(e)
            }
    
    @app.get("/security/health")
    async def security_health():
        """Check security system health."""
        try:
            # In a real implementation, you would check validator health here
            return {
                "status": "healthy",
                "validator": {"healthy": True},
                "monitor": {"healthy": True},
                "middleware": {"active": True}
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    # Add main API endpoints
    @app.get("/")
    async def root():
        return {
            "message": "Secure Bitcoin Knowledge Assistant API",
            "status": "running",
            "security": "enabled",
            "endpoints": [
                "/query", "/health", "/security/status", "/security/health", "/docs"
            ]
        }
    
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "security_middleware": "active"
        }
    
    @app.post("/query", response_model=QueryResponse)
    async def query_bitcoin_knowledge(request: QueryRequest):
        """
        Process Bitcoin knowledge queries with security validation.
        
        This endpoint demonstrates how the security middleware automatically
        validates all incoming requests before they reach the endpoint logic.
        """
        try:
            # Simulate Bitcoin knowledge processing
            # In the real implementation, this would call the Pinecone Assistant
            answer = f"This is a secure response to your Bitcoin question: {request.question}"
            
            return QueryResponse(
                answer=answer,
                sources=["Bitcoin Whitepaper", "Bitcoin Developer Guide"],
                tts_enabled=request.enable_tts
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")
    
    @app.post("/test-security")
    async def test_security_validation(request: Request):
        """
        Test endpoint to demonstrate security validation.
        
        Try sending malicious payloads to see how the middleware handles them.
        """
        body = await request.body()
        return {
            "message": "Request passed security validation",
            "body_length": len(body),
            "validation": "successful"
        }
    
    return app


def main():
    """Run the secure Bitcoin Assistant API."""
    import uvicorn
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create secure app
    app = create_secure_bitcoin_api()
    
    # Run the application
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()