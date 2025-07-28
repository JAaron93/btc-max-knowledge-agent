"""
Tests for security infrastructure and core interfaces.

This module tests the basic security infrastructure setup including
configuration management, data models, and interface definitions.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import os

from src.security import (
    SecurityConfiguration,
    SecurityConfigurationManager,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
    SecurityAction,
    SecurityViolation,
    ValidationResult,
    DetectionResult,
    AuthResult,
    AuthenticationStatus,
    TokenBucket,
    ResourceMetrics
)


class TestSecurityConfiguration:
    """Test security configuration data model."""
    
    def test_default_configuration_is_valid(self):
        """Test that default configuration passes validation."""
        config = SecurityConfiguration()
        errors = config.validate()
        assert len(errors) == 0, f"Default configuration should be valid, but got errors: {errors}"
    
    def test_invalid_configuration_detection(self):
        """Test that invalid configurations are detected."""
        config = SecurityConfiguration(
            max_query_length=-1,  # Invalid: negative value
            injection_detection_threshold=1.5,  # Invalid: > 1.0
            cpu_threshold_percent=150.0  # Invalid: > 100.0
        )
        
        errors = config.validate()
        assert len(errors) > 0, "Invalid configuration should produce validation errors"
        
        # Check specific error messages
        error_messages = ' '.join(errors)
        assert "max_query_length must be positive" in error_messages
        assert "injection_detection_threshold must be between 0.0 and 1.0" in error_messages
        assert "cpu_threshold_percent must be between 0.0 and 100.0" in error_messages
    
    def test_api_key_length_validation(self):
        """Test API key length constraint validation."""
        config = SecurityConfiguration(
            api_key_min_length=64,
            api_key_max_length=32  # Invalid: min > max
        )
        
        errors = config.validate()
        assert any("api_key_min_length must be less than api_key_max_length" in error for error in errors)
    
    def test_environment_validation(self):
        """Test environment setting validation."""
        config = SecurityConfiguration(environment="invalid_env")
        
        errors = config.validate()
        assert any("environment must be one of: development, staging, production" in error for error in errors)


class TestSecurityConfigurationManager:
    """Test security configuration manager."""
    
    @pytest.fixture
    def config_manager(self):
        """Create a configuration manager instance."""
        return SecurityConfigurationManager()
    
    @pytest.mark.asyncio
    async def test_load_default_config(self, config_manager):
        """Test loading default configuration."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test:test@localhost/test'}, clear=False):
            config = await config_manager.load_secure_config()
            
            assert isinstance(config, SecurityConfiguration)
            assert config.max_query_length == 4096
            assert config.rate_limit_per_minute == 100
            assert config.environment == "development"
    
    @pytest.mark.asyncio
    async def test_environment_variable_override(self, config_manager):
        """Test that environment variables override defaults."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test',
            'MAX_QUERY_LENGTH': '8192',
            'RATE_LIMIT_PER_MINUTE': '200',
            'ENVIRONMENT': 'production'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = await config_manager.load_secure_config()
            
            assert config.max_query_length == 8192
            assert config.rate_limit_per_minute == 200
            assert config.environment == "production"
    
    @pytest.mark.asyncio
    async def test_invalid_config_raises_error(self, config_manager):
        """Test that invalid configuration raises ValueError."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test',
            'MAX_QUERY_LENGTH': '-1'  # Invalid value
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            with pytest.raises(ValueError, match="Invalid security configuration"):
                await config_manager.load_secure_config()
    
    @pytest.mark.asyncio
    async def test_validate_environment_variables(self, config_manager):
        """Test environment variable validation."""
        # Test with missing required variable
        with patch.dict(os.environ, {}, clear=True):
            result = await config_manager.validate_environment_variables()
            
            assert not result.is_valid
            assert any(v.violation_type == "missing_environment_variable" for v in result.violations)
        
        # Test with invalid numeric value
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test',
            'MAX_QUERY_LENGTH': 'not_a_number'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            result = await config_manager.validate_environment_variables()
            
            assert not result.is_valid
            assert any("not a valid number" in v.description for v in result.violations)


class TestSecurityModels:
    """Test security data models."""
    
    def test_security_event_creation(self):
        """Test security event model creation."""
        event = SecurityEvent(
            event_type=SecurityEventType.AUTHENTICATION_FAILURE,
            severity=SecuritySeverity.WARNING,
            source_ip="192.168.1.1",
            details={"reason": "invalid_credentials"}
        )
        
        assert event.event_type == SecurityEventType.AUTHENTICATION_FAILURE
        assert event.severity == SecuritySeverity.WARNING
        assert event.source_ip == "192.168.1.1"
        assert event.details["reason"] == "invalid_credentials"
        assert event.event_id is not None
        assert isinstance(event.timestamp, datetime)
    
    def test_security_event_to_dict(self):
        """Test security event serialization."""
        event = SecurityEvent(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            severity=SecuritySeverity.ERROR,
            client_id="test_client"
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["event_type"] == "rate_limit_exceeded"
        assert event_dict["severity"] == "error"
        assert event_dict["client_id"] == "test_client"
        assert "timestamp" in event_dict
        assert "event_id" in event_dict
    
    def test_validation_result_confidence_score_validation(self):
        """Test validation result confidence score constraints."""
        # Valid confidence score
        result = ValidationResult(is_valid=True, confidence_score=0.8)
        assert result.confidence_score == 0.8
        
        # Invalid confidence scores should raise ValueError
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            ValidationResult(is_valid=True, confidence_score=1.5)
        
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            ValidationResult(is_valid=True, confidence_score=-0.1)
    
    def test_security_violation_creation(self):
        """Test security violation model."""
        violation = SecurityViolation(
            violation_type="sql_injection",
            severity=SecuritySeverity.CRITICAL,
            description="SQL injection attempt detected",
            detected_pattern="'; DROP TABLE",
            confidence_score=0.95,
            location="query_parameter",
            suggested_fix="Use parameterized queries"
        )
        
        assert violation.violation_type == "sql_injection"
        assert violation.severity == SecuritySeverity.CRITICAL
        assert violation.confidence_score == 0.95
        assert violation.detected_pattern == "'; DROP TABLE"
    
    def test_auth_result_risk_score_validation(self):
        """Test authentication result risk score validation."""
        # Valid risk score
        auth_result = AuthResult(
            status=AuthenticationStatus.SUCCESS,
            client_id="test_client",
            risk_score=0.3
        )
        assert auth_result.risk_score == 0.3
        
        # Invalid risk score should raise ValueError
        with pytest.raises(ValueError, match="Risk score must be between 0.0 and 1.0"):
            AuthResult(
                status=AuthenticationStatus.SUCCESS,
                client_id="test_client",
                risk_score=1.2
            )


class TestTokenBucket:
    """Test token bucket rate limiting model."""
    
    def test_token_bucket_creation(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(capacity=10, tokens=10.0, refill_rate=1.0)
        
        assert bucket.capacity == 10
        assert bucket.tokens == 10.0
        assert bucket.refill_rate == 1.0
        assert isinstance(bucket.last_refill, datetime)
    
    def test_token_consumption(self):
        """Test token consumption logic."""
        bucket = TokenBucket(capacity=10, tokens=5.0, refill_rate=1.0)
        
        # Should be able to consume available tokens
        assert bucket.consume(3) is True
        assert bucket.tokens == 2.0
        
        # Should not be able to consume more tokens than available
        assert bucket.consume(5) is False
        assert bucket.tokens == 2.0  # Tokens should remain unchanged
    
    def test_token_refill(self):
        """Test token bucket refill mechanism."""
        bucket = TokenBucket(capacity=10, tokens=0.0, refill_rate=2.0)
        
        # Mock time passage
        with patch('src.security.models.datetime') as mock_datetime:
            # Set initial time
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            bucket.last_refill = initial_time
            
            # Mock current time to be 1 second later
            later_time = datetime(2024, 1, 1, 12, 0, 1)
            mock_datetime.now.return_value = later_time
            
            # Trigger refill by calling consume() which internally calls _refill()
            # Try to consume 1 token - this should succeed after refill
            result = bucket.consume(1)
            
            # Should have succeeded because refill added 2 tokens
            assert result is True
            # Should have 1 token remaining (2 added - 1 consumed)
            assert bucket.tokens == 1.0
            assert bucket.last_refill == later_time
    
    def test_token_bucket_capacity_limit(self):
        """Test that token bucket doesn't exceed capacity."""
        bucket = TokenBucket(capacity=5, tokens=3.0, refill_rate=10.0)
        
        # Mock significant time passage
        with patch('src.security.models.datetime') as mock_datetime:
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            bucket.last_refill = initial_time
            
            # Mock time 10 seconds later (would add 100 tokens without limit)
            later_time = datetime(2024, 1, 1, 12, 0, 10)
            mock_datetime.now.return_value = later_time
            
            # Trigger refill by calling get_wait_time() which internally calls _refill()
            wait_time = bucket.get_wait_time(1)
            
            # Should be capped at capacity
            assert bucket.tokens == 5.0
            # Should not need to wait since we have enough tokens
            assert wait_time == 0.0


class TestResourceMetrics:
    """Test resource metrics model."""
    
    def test_resource_metrics_creation(self):
        """Test resource metrics initialization."""
        metrics = ResourceMetrics(
            cpu_percent=75.0,
            memory_percent=60.0,
            disk_percent=40.0,
            active_connections=25,
            response_time_ms=150.0,
            error_rate_percent=2.5
        )
        
        assert metrics.cpu_percent == 75.0
        assert metrics.memory_percent == 60.0
        assert metrics.active_connections == 25
        assert isinstance(metrics.timestamp, datetime)
    
    def test_threshold_checking(self):
        """Test resource threshold checking."""
        config = SecurityConfiguration(
            cpu_threshold_percent=80.0,
            memory_threshold_percent=85.0,
            disk_threshold_percent=90.0
        )
        config.set_alert_threshold("error_rate_percent", 5.0)
        config.set_alert_threshold("response_time_seconds", 2.0)
        
        # Metrics within thresholds
        metrics = ResourceMetrics(
            cpu_percent=70.0,
            memory_percent=75.0,
            disk_percent=80.0,
            error_rate_percent=3.0,
            response_time_ms=1500.0
        )
        
        exceeded = metrics.exceeds_thresholds(config)
        assert len(exceeded) == 0
        
        # Metrics exceeding thresholds
        metrics = ResourceMetrics(
            cpu_percent=85.0,  # Exceeds 80%
            memory_percent=90.0,  # Exceeds 85%
            disk_percent=95.0,  # Exceeds 90%
            error_rate_percent=7.0,  # Exceeds 5%
            response_time_ms=3000.0  # Exceeds 2000ms (2 seconds configured in line 320)

        )
        
        exceeded = metrics.exceeds_thresholds(config)
        expected_exceeded = [
            "cpu_threshold_percent",
            "memory_threshold_percent", 
            "disk_threshold_percent",
            "error_rate_percent",
            "response_time_seconds"
        ]
        
        for threshold in expected_exceeded:
            assert threshold in exceeded, f"Expected {threshold} to be exceeded"


if __name__ == "__main__":
    pytest.main([__file__])