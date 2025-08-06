"""
Demonstration of security middleware integration with Bitcoin Assistant API.

This module shows how to integrate the security validation middleware
with the existing FastAPI application.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .config import SecurityConfigurationManager
from .middleware import create_security_middleware
from .models import Anomaly, SecurityEvent, SecuritySeverity
from .validator import SecurityValidator

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, max_length=1000, description="Bitcoin-related question"
    )
    enable_tts: Optional[bool] = False


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    tts_enabled: bool = False


class MockSecurityMonitor:
    """
    Mock security monitor for demonstration purposes.

    This mock implementation provides realistic behavior for testing and demo
    scenarios while maintaining simplicity. It includes:

    - Proper type hints for all method signatures
    - Event tracking and counting for realistic metrics
    - Simulated anomaly detection logic
    - Comprehensive metrics generation
    - Appropriate logging levels based on event severity

    In production, this would be replaced with a real security monitoring
    implementation that integrates with external monitoring systems,
    databases, and alerting platforms.

    Example Production Features (not implemented in mock):
    - Persistent event storage (database, time-series DB)
    - Real-time anomaly detection algorithms
    - Integration with alerting systems (PagerDuty, Slack, email)
    - Dashboard and visualization support
    - Advanced analytics and threat intelligence
    - Compliance reporting and audit trails
    """

    def __init__(self) -> None:
        """Initialize the mock security monitor with tracking state."""
        self._event_log: List[SecurityEvent] = []
        self._start_time: float = time.time()
        self._event_counts: Dict[str, int] = {}
        self._last_anomaly_check: float = time.time()

    async def log_security_event(self, event: SecurityEvent) -> None:
        """
        Log a security event with realistic tracking.

        Args:
            event: SecurityEvent to be logged
        """
        # Store the event for metrics
        self._event_log.append(event)

        # Update event counts by type
        event_type = event.event_type.value
        self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1

        # Log with appropriate level based on severity
        log_message = (
            f"Security event: {event.event_type.value} "
            f"[{event.severity.value.upper()}] "
            f"from {event.source_ip or 'unknown'}"
        )

        if event.severity.value in ["critical", "error"]:
            logger.error(log_message)
        elif event.severity.value == "warning":
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Add details if available
        if event.details:
            logger.debug(f"Event details: {event.details}")

    async def detect_anomalies(self, metrics: Dict[str, Any]) -> List[Anomaly]:
        """
        Detect anomalies in security metrics with mock logic.

        Args:
            metrics: Dictionary of security metrics to analyze

        Returns:
            List of detected anomalies
        """
        anomalies: List[Anomaly] = []
        current_time = time.time()

        # Mock anomaly detection based on event frequency
        if len(self._event_log) > 0:
            recent_events = [
                event
                for event in self._event_log
                if (current_time - event.timestamp.timestamp()) < 300  # Last 5 minutes
            ]

            # Simulate anomaly detection for high event frequency
            if len(recent_events) > 10:
                # Create actual Anomaly object
                anomaly = Anomaly(
                    anomaly_type="high_event_frequency",
                    severity=SecuritySeverity.WARNING,
                    description=f"High security event frequency: {len(recent_events)} events in 5 minutes",
                    timestamp=datetime.now(),
                    metrics={
                        "event_count": float(len(recent_events)),
                        "time_window": 300.0,
                        "threshold_value": 10.0,
                        "current_value": float(len(recent_events)),
                        "deviation_percent": ((len(recent_events) - 10) / 10) * 100,
                    },
                    threshold_exceeded="event_frequency_threshold",
                    recommended_actions=[
                        "Review recent security events for patterns",
                        "Consider implementing additional rate limiting",
                        "Monitor for potential security incidents",
                    ],
                )
                anomalies.append(anomaly)

        self._last_anomaly_check = current_time
        return anomalies

    async def generate_alert(self, anomaly: Any) -> None:
        """
        Generate an alert for a detected anomaly.

        Args:
            anomaly: Anomaly object or data that triggered the alert
        """
        if isinstance(anomaly, dict):
            alert_message = f"Security Alert: {anomaly.get('type', 'unknown')} - {anomaly.get('description', 'No description')}"
        else:
            alert_message = f"Security alert: {anomaly}"

        logger.warning(alert_message)

        # In a real implementation, this would:
        # - Send notifications (email, Slack, PagerDuty, etc.)
        # - Update alert dashboards
        # - Trigger automated responses
        # - Log to external monitoring systems

    async def get_security_metrics(self, time_range: int = 3600) -> Dict[str, Any]:
        """
        Get security metrics for the specified time range.

        Args:
            time_range: Time range in seconds (default: 1 hour)

        Returns:
            Dictionary of security metrics with realistic mock data
        """
        current_time = time.time()
        start_time = current_time - time_range

        # Filter events within the time range
        recent_events = [
            event
            for event in self._event_log
            if event.timestamp.timestamp() >= start_time
        ]

        # Calculate metrics by event type
        event_type_counts = {}
        severity_counts = {"info": 0, "warning": 0, "error": 0, "critical": 0}

        for event in recent_events:
            # Count by event type
            event_type = event.event_type.value
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

            # Count by severity
            severity = event.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Calculate rates
        hours = time_range / 3600
        total_events = len(recent_events)
        events_per_hour = total_events / hours if hours > 0 else 0

        # Mock additional metrics that would come from real monitoring
        uptime_seconds = current_time - self._start_time

        return {
            "time_range_seconds": time_range,
            "total_events": total_events,
            "events_per_hour": round(events_per_hour, 2),
            "event_types": event_type_counts,
            "severity_distribution": severity_counts,
            "uptime_seconds": round(uptime_seconds, 2),
            "last_event_time": (
                recent_events[-1].timestamp.isoformat() if recent_events else None
            ),
            "anomaly_checks_performed": 1,  # Mock value
            "alerts_generated": 0,  # Mock value
            "system_health": "healthy",  # Mock value
            "monitoring_active": True,
            "collection_timestamp": datetime.now().isoformat(),
        }


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

    # Initialize security state tracking
    security_state = {
        "enabled": False,
        "validator": None,
        "monitor": None,
        "config": None,
        "middleware_applied": False,
        "initialization_error": None,
    }

    try:
        # Load security configuration
        config_manager = SecurityConfigurationManager()
        security_config = config_manager.load_secure_config()
        security_state["config"] = security_config

        # Initialize security components
        validator = SecurityValidator(security_config)
        monitor = (
            MockSecurityMonitor()
        )  # Replace with actual SecurityMonitor when implemented
        security_state["validator"] = validator
        security_state["monitor"] = monitor

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
                "/security/health",
            ],
        )

        app.add_middleware(validation_middleware)
        app.add_middleware(headers_middleware)

        security_state["enabled"] = True
        security_state["middleware_applied"] = True
    except Exception as e:
        security_state["initialization_error"] = str(e)
        # In production, you might want to fail here
        # For demo purposes, we'll continue without security
        logger.warning("Running without security middleware")

    # Add security status endpoints
    @app.get("/security/status")
    async def security_status():
        """
        Get security system status with dynamic values.

        Returns real-time status of security components instead of hardcoded values.
        This endpoint reflects the actual state of the validator, monitor, and
        middleware components based on their initialization and health.
        """
        try:
            # Get validator status and library information
            validator_status = "inactive"
            validator_libraries = {}
            if security_state["validator"]:
                validator_status = "active"
                try:
                    validator_libraries = security_state[
                        "validator"
                    ].get_library_status()
                except Exception as e:
                    logger.warning(f"Failed to get validator library status: {e}")

            # Get monitor status and metrics
            monitor_status = "inactive"
            monitor_metrics = {}
            if security_state["monitor"]:
                monitor_status = "active"
                try:
                    monitor_metrics = await security_state[
                        "monitor"
                    ].get_security_metrics()
                except Exception as e:
                    logger.warning(f"Failed to get monitor metrics: {e}")

            # Get configuration status
            config_status = {}
            if security_state["config"]:
                config_status = {
                    "max_query_length": security_state["config"].max_query_length,
                    "max_metadata_fields": security_state["config"].max_metadata_fields,
                    "monitoring_enabled": security_state["config"].monitoring_enabled,
                    "environment": security_state["config"].environment,
                }

            return {
                "security_enabled": security_state["enabled"],
                "validator_status": validator_status,
                "validator_libraries": validator_libraries,
                "monitor_status": monitor_status,
                "monitor_metrics": monitor_metrics,
                "middleware_applied": security_state["middleware_applied"],
                "configuration": config_status,
                "initialization_error": security_state["initialization_error"],
            }
        except Exception as e:
            return {"security_enabled": False, "error": str(e)}

    @app.get("/security/health")
    async def security_health():
        """
        Check security system health with comprehensive diagnostics.

        Performs actual health checks on security components and returns
        detailed status information including library availability, error states,
        and component-specific health metrics.
        """
        try:
            overall_status = "healthy"
            validator_health = {"healthy": False, "error": None}
            monitor_health = {"healthy": False, "error": None}
            middleware_health = {"active": security_state["middleware_applied"]}

            # Check validator health
            if security_state["validator"]:
                try:
                    library_health = await security_state[
                        "validator"
                    ].check_library_health()
                    validator_health = {
                        "healthy": len(library_health.health_check_errors) == 0,
                        "errors": library_health.health_check_errors,
                        "libraries": {
                            "libinjection": library_health.libinjection_available,
                            "bleach": library_health.bleach_available,
                            "markupsafe": library_health.markupsafe_available,
                        },
                        "last_check": library_health.last_health_check,
                    }
                    if not validator_health["healthy"]:
                        overall_status = "degraded"
                except Exception as e:
                    validator_health = {"healthy": False, "error": str(e)}
                    overall_status = "unhealthy"
            else:
                validator_health = {
                    "healthy": False,
                    "error": "Validator not initialized",
                }
                overall_status = "unhealthy"

            # Check monitor health
            if security_state["monitor"]:
                try:
                    # For MockSecurityMonitor, we'll assume it's healthy
                    # In a real implementation, you would check actual monitor health
                    monitor_health = {"healthy": True}
                except Exception as e:
                    monitor_health = {"healthy": False, "error": str(e)}
                    overall_status = "unhealthy"
            else:
                monitor_health = {"healthy": False, "error": "Monitor not initialized"}
                overall_status = "unhealthy"

            # Check if there was an initialization error
            if security_state["initialization_error"]:
                overall_status = "unhealthy"

            return {
                "status": overall_status,
                "validator": validator_health,
                "monitor": monitor_health,
                "middleware": middleware_health,
                "initialization_error": security_state["initialization_error"],
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # Add main API endpoints
    @app.get("/")
    async def root():
        return {
            "message": "Secure Bitcoin Knowledge Assistant API",
            "status": "running",
            "security_middleware": (
                "active" if security_state["enabled"] else "inactive"
            ),
            "endpoints": [
                "/query",
                "/health",
                "/security/status",
                "/security/health",
                "/docs",
            ],
        }

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "security_middleware": (
                "active" if security_state["enabled"] else "inactive"
            ),
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
                tts_enabled=request.enable_tts,
            )

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Query processing failed: {str(e)}"
            )

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
            "validation": "successful",
        }

    return app


def main():
    """Run the secure Bitcoin Assistant API."""
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create secure app
    app = create_secure_bitcoin_api()

    # Run the application
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
