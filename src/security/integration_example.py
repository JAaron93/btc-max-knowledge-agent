"""
Example integration of security middleware with existing FastAPI application.

This module demonstrates how to integrate the security validation middleware
with the existing Bitcoin Assistant API.
"""

import logging
from typing import Optional

from fastapi import FastAPI

from .middleware import create_security_middleware
from .validator import SecurityValidator
from .monitor import SecurityMonitor  # This will be implemented in future tasks
from .config import SecurityConfigurationManager
from .models import SecurityConfiguration


logger = logging.getLogger(__name__)


class SecurityIntegration:
    """
    Helper class to integrate security middleware with FastAPI applications.
    
    This class handles the setup and configuration of all security components
    needed for the middleware integration.
    """
    
    def __init__(self, app: FastAPI, config: Optional[SecurityConfiguration] = None):
        """
        Initialize security integration.
        
        Args:
            app: FastAPI application instance
            config: Optional security configuration (will load from env if None)
        """
        self.app = app
        self.config = config or self._load_security_config()
        
        # Initialize security components
        self.validator = SecurityValidator(self.config)
        self.monitor = self._create_security_monitor()
        
        # Create middleware
        self.validation_middleware, self.headers_middleware = create_security_middleware(
            self.validator,
            self.monitor,
            self.config,
            exempt_paths=self._get_exempt_paths()
        )
    
    def _load_security_config(self) -> SecurityConfiguration:
        """Load security configuration from environment."""
        config_manager = SecurityConfigurationManager()
        return config_manager.load_secure_config()
    
    def _create_security_monitor(self):
        """Create security monitor instance."""
        # For now, return a mock monitor since SecurityMonitor is not implemented yet
        # This will be replaced with actual SecurityMonitor in future tasks
        class MockSecurityMonitor:
            async def log_security_event(self, event):
                logger.info(f"Security event: {event.event_type.value} - {event.severity.value}")
            
            async def detect_anomalies(self, metrics):
                return []
            
            async def generate_alert(self, anomaly):
                logger.warning(f"Security alert: {anomaly}")
            
            async def get_security_metrics(self, time_range=3600):
                return {"events": 0}
        
        return MockSecurityMonitor()
    
    def _get_exempt_paths(self) -> list:
        """Get list of paths exempt from security validation."""
        return [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico",
            "/static",
            "/tts/status",  # TTS status endpoint
            "/tts/streaming/status"  # Streaming status endpoint
        ]
    
    def apply_security_middleware(self) -> None:
        """Apply security middleware to the FastAPI application."""
        try:
            # Add validation middleware first (processes requests)
            self.app.add_middleware(self.validation_middleware)
            
            # Add headers middleware second (processes responses)
            self.app.add_middleware(self.headers_middleware)
            
            logger.info("Security middleware applied successfully")
            
        except Exception as e:
            logger.error(f"Failed to apply security middleware: {e}")
            raise
    
    def get_security_status(self) -> dict:
        """Get current security system status."""
        return {
            "validator_enabled": True,
            "monitor_enabled": True,
            "middleware_applied": True,
            "config": {
                "max_query_length": self.config.max_query_length,
                "max_metadata_fields": self.config.max_metadata_fields,
                "monitoring_enabled": self.config.monitoring_enabled,
                "environment": self.config.environment
            },
            "library_status": self.validator.get_library_status()
        }


def integrate_security_with_bitcoin_api(app: FastAPI) -> SecurityIntegration:
    """
    Integrate security middleware with the Bitcoin Assistant API.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        SecurityIntegration instance for further configuration
    """
    try:
        # Create security integration
        security = SecurityIntegration(app)
        
        # Apply middleware
        security.apply_security_middleware()
        
        # Add security status endpoint
        @app.get("/security/status")
        async def security_status():
            """Get security system status."""
            return security.get_security_status()
        
        @app.get("/security/health")
        async def security_health():
            """Check security system health."""
            try:
                # Check validator health
                library_health = await security.validator.check_library_health()
                
                return {
                    "status": "healthy",
                    "validator": {
                        "healthy": len(library_health.health_check_errors) == 0,
                        "errors": library_health.health_check_errors,
                        "libraries": {
                            "libinjection": library_health.libinjection_available,
                            "bleach": library_health.bleach_available,
                            "markupsafe": library_health.markupsafe_available
                        }
                    },
                    "monitor": {"healthy": True},  # Mock for now
                    "middleware": {"active": True}
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        logger.info("Security integration completed successfully")
        return security
        
    except Exception as e:
        logger.error(f"Security integration failed: {e}")
        raise


# Example usage for existing bitcoin_assistant_api.py
def example_integration():
    """
    Example of how to integrate security with existing API.
    
    This would be added to the existing bitcoin_assistant_api.py file.
    """
    from fastapi import FastAPI
    
    # Create FastAPI app (this already exists in bitcoin_assistant_api.py)
    app = FastAPI(
        title="Bitcoin Knowledge Assistant",
        description="AI-powered Bitcoin and blockchain knowledge assistant with security",
        version="1.0.0",
    )
    
    # Integrate security middleware
    try:
        security_integration = integrate_security_with_bitcoin_api(app)
        logger.info("Security middleware integrated successfully")
    except Exception as e:
        logger.error(f"Failed to integrate security: {e}")
        # Continue without security middleware in development
        if app.debug:
            logger.warning("Running without security middleware in debug mode")
        else:
            raise
    
    # Rest of the existing API code would follow...
    # (BitcoinAssistantService, endpoints, etc.)
    
    return app


if __name__ == "__main__":
    # Example of running with security integration
    app = example_integration()
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)