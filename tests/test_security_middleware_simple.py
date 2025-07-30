"""
Simple integration tests for security validation middleware.

This module tests the FastAPI security middleware functionality without
importing problematic modules.
"""

import json
import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import only the specific modules we need
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from security.middleware import (
    SecurityValidationMiddleware,
    SecurityHeadersMiddleware,
    create_security_middleware
)
from security.models import (
    ValidationResult,
    SecurityViolation,
    SecuritySeverity,
    SecurityAction,
    SecurityConfiguration,
    SecurityEvent,
    SecurityEventType
)
from security.interfaces import ISecurityValidator, ISecurityMonitor


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
            recommended_action=SecurityAction.ALLOW
        )
    
    def set_validation_result(self, input_data: str, result: ValidationResult):
        """Set specific validation result for input data."""
        self.validation_results[input_data] = result
    
    async def validate_input(self, input_data: str, context: Dict[str, Any]) -> ValidationResult:
        """Mock validate_input method."""
        self.validate_input_calls.append((input_data, context))
        return self.validation_results.get(input_data, self.default_result)
    
    async def sanitize_input(self, input_data: str) -> str:
        """Mock sanitize_input method."""
        self.sanitize_input_calls.append(input_data)
        return input_data.replace("<script>", "&lt;script&gt;")
    
    async def validate_query_parameters(self, params: Dict[str, Any]) -> ValidationResult:
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
        environment="test"
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
    async def query(request):
        body = await request.body()
        return {"query": body.decode('utf-8') if body else ""}
    
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
        response = client.get("/health")
        assert response.status_code == 200
        
        # Should not call validator for exempt paths
        assert len(mock_validator.validate_input_calls) == 0
    
    def test_valid_request_passes_validation(self, test_app, mock_validator, mock_monitor):
        """Test that valid requests pass through middleware."""
        client = TestClient(test_app)
        
        # Set up validator to return valid result
        mock_validator.default_result = ValidationResult(
            is_valid=True,
            confidence_score=1.0,
            violations=[],
            recommended_action=SecurityAction.ALLOW
        )
        
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json() == {"message": "Hello World"}
    
    def test_invalid_request_blocked(self, test_app, mock_validator, mock_monitor):
        """Test that invalid requests are blocked."""
        client = TestClient(test_app)
        
        # Set up validator to return invalid result
        violation = SecurityViolation(
            violation_type="xss_injection",
            severity=SecuritySeverity.CRITICAL,
            description="XSS script detected",
            confidence_score=0.95,
            detected_pattern="<script>alert('xss')</script>"
        )
        
        invalid_result = ValidationResult(
            is_valid=False,
            confidence_score=0.95,
            violations=[violation],
            recommended_action=SecurityAction.BLOCK
        )
        
        malicious_payload = '{"query": "<script>alert(\'xss\')</script>"}'
        mock_validator.set_validation_result(malicious_payload, invalid_result)
        
        response = client.post(
            "/query",
            content=malicious_payload,
            headers={"content-type": "application/json"}
        )
        
        assert response.status_code == 400
        response_data = response.json()
        assert response_data["error"] == "input_validation_failed"
        assert "request_id" in response_data
        assert response_data["violations"] == 1
        
        # Check that validation failure was logged
        failure_events = [
            event for event in mock_monitor.logged_events
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
            confidence_score=0.8
        )
        
        sanitize_result = ValidationResult(
            is_valid=False,
            confidence_score=0.8,
            violations=[violation],
            recommended_action=SecurityAction.SANITIZE
        )
        
        html_payload = '{"query": "<b>bold text</b>"}'
        mock_validator.set_validation_result(html_payload, sanitize_result)
        
        response = client.post(
            "/query",
            content=html_payload,
            headers={"content-type": "application/json"}
        )
        
        assert response.status_code == 400
        response_data = response.json()
        assert response_data["error"] == "input_sanitization_required"


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
            "Permissions-Policy"
        ]
        
        for header in expected_headers:
            assert header in response.headers
        
        # Check specific header values
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


if __name__ == "__main__":
    pytest.main([__file__])