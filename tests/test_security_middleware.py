"""
Integration tests for security validation middleware.

This module tests the FastAPI security middleware functionality including
request validation, error handling, and security event logging.
"""

import asyncio
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from src.security.interfaces import ISecurityMonitor, ISecurityValidator
from src.security.middleware import (SecurityHeadersMiddleware,
                                     SecurityValidationMiddleware,
                                     create_security_middleware)
from src.security.models import (SecurityAction, SecurityConfiguration,
                                 SecurityEvent, SecurityEventType,
                                 SecuritySeverity, SecurityViolation,
                                 ValidationResult)


class MockSecurityValidator(ISecurityValidator):
    """Mock security validator for testing."""

    def __init__(self):
        self.validate_input_calls = []
        self.validate_query_parameters_calls = []
        self.sanitize_input_calls = []
        self.validation_results = {}
        self.default_result = ValidationResult(
            is_valid=True,
            confidence_score=1.0,
            violations=[],
            recommended_action=SecurityAction.ALLOW,
        )

    def set_validation_result(self, input_data: str, result: ValidationResult):
        """Set specific validation result for input data."""
        self.validation_results[input_data] = result

    async def validate_input(
        self, input_data: str, context: Dict[str, Any]
    ) -> ValidationResult:
        """Mock validate_input method."""
        self.validate_input_calls.append((input_data, context))
        return self.validation_results.get(input_data, self.default_result)

    async def sanitize_input(self, input_data: str) -> str:
        """Mock sanitize_input method."""
        self.sanitize_input_calls.append(input_data)
        return input_data.replace("<script>", "&lt;script&gt;")

    async def validate_query_parameters(
        self, params: Dict[str, Any]
    ) -> ValidationResult:
        """Mock validate_query_parameters method."""
        self.validate_query_parameters_calls.append(params)
        return self.default_result


class MockSecurityMonitor(ISecurityMonitor):
    """Mock security monitor for testing."""

    def __init__(self):
        self.logged_events = []
        self.detected_anomalies = []
        self.generated_alerts = []

    async def log_security_event(self, event: SecurityEvent) -> None:
        """Mock log_security_event method."""
        self.logged_events.append(event)

    async def detect_anomalies(self, metrics: Dict[str, Any]) -> list:
        """Mock detect_anomalies method."""
        return self.detected_anomalies

    async def generate_alert(self, anomaly) -> None:
        """Mock generate_alert method."""
        self.generated_alerts.append(anomaly)

    async def get_security_metrics(self, time_range: int = 3600) -> Dict[str, Any]:
        """Mock get_security_metrics method."""
        return {"events": len(self.logged_events)}


@pytest.fixture
def mock_validator():
    """Create mock security validator."""
    return MockSecurityValidator()


@pytest.fixture
def mock_monitor():
    """Create mock security monitor."""
    return MockSecurityMonitor()


@pytest.fixture
def security_config():
    """Create test security configuration."""
    return SecurityConfiguration(
        max_query_length=4096,
        max_metadata_fields=50,
        monitoring_enabled=True,
        environment="test",
    )


@pytest.fixture
def test_app(mock_validator, mock_monitor, security_config):
    """Create test FastAPI app with security middleware."""
    app = FastAPI()

    # Add security middleware
    validation_middleware, headers_middleware = create_security_middleware(
        mock_validator, mock_monitor, security_config
    )

    app.add_middleware(validation_middleware)
    app.add_middleware(headers_middleware)

    # Add test endpoints
    @app.get("/")
    async def root():
        return {"message": "Hello World"}

    @app.post("/query")
    async def query(request: Request):
        body = await request.body()
        return {"query": body.decode("utf-8") if body else ""}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


class TestSecurityValidationMiddleware:
    """Test cases for SecurityValidationMiddleware."""

    def test_exempt_paths_bypass_validation(self, test_app, mock_validator):
        """Test that exempt paths bypass security validation."""
        client = TestClient(test_app)

        # Test exempt paths
        exempt_paths = ["/health", "/docs", "/openapi.json"]

        for path in exempt_paths:
            response = client.get(path)
            # Should not call validator for exempt paths
            assert len(mock_validator.validate_input_calls) == 0

    def test_valid_request_passes_validation(
        self, test_app, mock_validator, mock_monitor
    ):
        """Test that valid requests pass through middleware."""
        client = TestClient(test_app)

        # Set up validator to return valid result
        mock_validator.default_result = ValidationResult(
            is_valid=True,
            confidence_score=1.0,
            violations=[],
            recommended_action=SecurityAction.ALLOW,
        )

        response = client.get("/")

        assert response.status_code == 200
        assert response.json() == {"message": "Hello World"}

        # Check that validation was called appropriately
        # For GET requests without body, input validation should not be called
        assert len(mock_validator.validate_input_calls) == 0

        # For GET requests without query parameters, query parameter validation should not be called
        assert len(mock_validator.validate_query_parameters_calls) == 0

        # Check that success event was logged
        # The middleware should always log INPUT_VALIDATION_SUCCESS for valid requests,
        # regardless of request method or presence of query parameters
        success_events = [
            event
            for event in mock_monitor.logged_events
            if event.event_type == SecurityEventType.INPUT_VALIDATION_SUCCESS
        ]

        # Assert that exactly one success event was logged
        assert (
            len(success_events) == 1
        ), f"Expected 1 success event, got {len(success_events)}"

        # Verify the success event properties
        success_event = success_events[0]
        assert success_event.event_type == SecurityEventType.INPUT_VALIDATION_SUCCESS
        assert success_event.severity == SecuritySeverity.INFO
        assert success_event.source_ip is not None
        assert success_event.details["validation_passed"] is True
        assert success_event.details["path"] == "/"
        assert success_event.details["method"] == "GET"

    def test_invalid_request_blocked(self, test_app, mock_validator, mock_monitor):
        """Test that invalid requests are blocked."""
        client = TestClient(test_app)

        # Set up validator to return invalid result
        violation = SecurityViolation(
            violation_type="xss_injection",
            severity=SecuritySeverity.CRITICAL,
            description="XSS script detected",
            confidence_score=0.95,
            detected_pattern="<script>alert('xss')</script>",
        )

        invalid_result = ValidationResult(
            is_valid=False,
            confidence_score=0.95,
            violations=[violation],
            recommended_action=SecurityAction.BLOCK,
        )

        malicious_payload = '{"query": "<script>alert(\'xss\')</script>"}'
        mock_validator.set_validation_result(malicious_payload, invalid_result)

        response = client.post(
            "/query",
            content=malicious_payload,
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 400
        response_data = response.json()
        assert response_data["error"] == "input_validation_failed"
        assert "request_id" in response_data
        assert response_data["violations"] == 1

        # Check that validation failure was logged
        failure_events = [
            event
            for event in mock_monitor.logged_events
            if event.event_type == SecurityEventType.INPUT_VALIDATION_FAILURE
        ]
        assert len(failure_events) > 0

        failure_event = failure_events[0]
        assert failure_event.severity == SecuritySeverity.CRITICAL
        assert len(failure_event.details["violations"]) == 1

    def test_sanitization_action_handling(self, test_app, mock_validator, mock_monitor):
        """Test handling of sanitization recommendation."""
        client = TestClient(test_app)

        # Set up validator to recommend sanitization
        violation = SecurityViolation(
            violation_type="html_injection",
            severity=SecuritySeverity.WARNING,
            description="HTML content detected",
            confidence_score=0.8,
        )

        sanitize_result = ValidationResult(
            is_valid=False,
            confidence_score=0.8,
            violations=[violation],
            recommended_action=SecurityAction.SANITIZE,
        )

        html_payload = '{"query": "<b>bold text</b>"}'
        mock_validator.set_validation_result(html_payload, sanitize_result)

        response = client.post(
            "/query", content=html_payload, headers={"content-type": "application/json"}
        )

        assert response.status_code == 400
        response_data = response.json()
        assert response_data["error"] == "input_sanitization_required"

    def test_query_parameter_validation(self, test_app, mock_validator):
        """Test validation of query parameters."""
        client = TestClient(test_app)

        # Set up validator to validate query parameters
        mock_validator.default_result = ValidationResult(
            is_valid=True,
            confidence_score=1.0,
            violations=[],
            recommended_action=SecurityAction.ALLOW,
        )

        response = client.get("/?search=bitcoin&limit=10")

        assert response.status_code == 200

        # Check that query parameters were validated
        assert len(mock_validator.validate_query_parameters_calls) > 0
        params_call = mock_validator.validate_query_parameters_calls[0]
        assert "search" in params_call
        assert "limit" in params_call

    def test_client_ip_extraction(self, test_app, mock_monitor):
        """Test client IP extraction from various headers."""
        client = TestClient(test_app)

        # Test with X-Forwarded-For header
        response = client.get(
            "/", headers={"X-Forwarded-For": "192.168.1.100, 10.0.0.1"}
        )

        assert response.status_code == 200

        # Check logged events for IP extraction
        if mock_monitor.logged_events:
            event = mock_monitor.logged_events[0]
            # Should extract first IP from forwarded header
            assert event.source_ip == "192.168.1.100"

    def test_request_context_extraction(self, test_app, mock_validator):
        """Test extraction of request context for validation."""
        client = TestClient(test_app)

        response = client.post(
            "/query",
            json={"query": "test"},
            headers={"User-Agent": "TestClient/1.0", "X-Real-IP": "203.0.113.1"},
        )

        assert response.status_code == 200

        # Check that context was passed to validator
        if mock_validator.validate_input_calls:
            _, context = mock_validator.validate_input_calls[0]
            assert context["method"] == "POST"
            assert context["path"] == "/query"
            assert context["user_agent"] == "TestClient/1.0"
            assert context["client_ip"] == "203.0.113.1"

    def test_error_handling_in_middleware(self, test_app, mock_validator, mock_monitor):
        """Test error handling when validator raises exceptions."""
        client = TestClient(test_app)

        # Make validator raise an exception
        async def failing_validate_input(input_data, context):
            raise Exception("Validator error")

        mock_validator.validate_input = failing_validate_input

        response = client.post("/query", json={"query": "test"})

        # Should return 500 error for internal errors
        assert response.status_code == 500
        response_data = response.json()
        assert response_data["error"] == "internal_server_error"
        assert "request_id" in response_data

        # Check that system error was logged
        error_events = [
            event
            for event in mock_monitor.logged_events
            if event.event_type == SecurityEventType.SYSTEM_ERROR
        ]
        assert len(error_events) > 0


class TestSecurityHeadersMiddleware:
    """Test cases for SecurityHeadersMiddleware."""

    def test_security_headers_added(self, test_app):
        """Test that security headers are added to responses."""
        client = TestClient(test_app)

        response = client.get("/")

        # Check for standard security headers
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "Referrer-Policy",
            "Permissions-Policy",
        ]

        for header in expected_headers:
            assert header in response.headers

        # Check specific header values
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]

    def test_production_headers(self, mock_validator, mock_monitor):
        """Test production-specific headers."""
        # Create production config
        prod_config = SecurityConfiguration(
            environment="production", monitoring_enabled=True
        )

        app = FastAPI()
        validation_middleware, headers_middleware = create_security_middleware(
            mock_validator, mock_monitor, prod_config
        )

        app.add_middleware(headers_middleware)

        @app.get("/")
        async def root():
            return {"message": "Hello"}

        client = TestClient(app)
        response = client.get("/")

        # Check production-specific headers
        assert response.headers.get("Server") == "BTC-Assistant"


class TestMiddlewareIntegration:
    """Integration tests for complete middleware stack."""

    def test_complete_request_flow(self, test_app, mock_validator, mock_monitor):
        """Test complete request flow through all middleware."""
        client = TestClient(test_app)

        # Set up successful validation
        mock_validator.default_result = ValidationResult(
            is_valid=True,
            confidence_score=1.0,
            violations=[],
            recommended_action=SecurityAction.ALLOW,
        )

        response = client.post(
            "/query",
            json={"query": "What is Bitcoin?"},
            headers={"User-Agent": "TestClient/1.0"},
        )

        assert response.status_code == 200

        # Check security headers are present
        assert "X-Content-Type-Options" in response.headers

        # Check that events were logged
        assert len(mock_monitor.logged_events) > 0

        # Should have validation success and request completion events
        event_types = [event.event_type for event in mock_monitor.logged_events]
        assert SecurityEventType.REQUEST_SUCCESS in event_types

    def test_middleware_factory_function(
        self, mock_validator, mock_monitor, security_config
    ):
        """Test middleware factory function."""
        validation_middleware, headers_middleware = create_security_middleware(
            mock_validator, mock_monitor, security_config, exempt_paths=["/custom"]
        )

        app = FastAPI()

        # Should be able to add middleware without errors
        app.add_middleware(validation_middleware)
        app.add_middleware(headers_middleware)

        @app.get("/custom")
        async def custom():
            return {"custom": True}

        client = TestClient(app)
        response = client.get("/custom")

        assert response.status_code == 200
        # Custom exempt path should not trigger validation
        assert len(mock_validator.validate_input_calls) == 0

    @pytest.mark.asyncio
    async def test_async_middleware_behavior(
        self, mock_validator, mock_monitor, security_config
    ):
        """Test async behavior of middleware."""
        app = FastAPI()

        validation_middleware, _ = create_security_middleware(
            mock_validator, mock_monitor, security_config
        )

        app.add_middleware(validation_middleware)

        @app.post("/async-endpoint")
        async def async_endpoint(request: Request):
            # Simulate async processing
            await asyncio.sleep(0.01)
            body = await request.body()
            return {"processed": True, "body_length": len(body)}

        client = TestClient(app)

        response = client.post(
            "/async-endpoint", json={"data": "test async processing"}
        )

        assert response.status_code == 200
        assert response.json()["processed"] is True

        # Check that async validation worked
        assert len(mock_monitor.logged_events) > 0


if __name__ == "__main__":
    pytest.main([__file__])
