#!/usr/bin/env python3
"""
Unit tests for SecurityValidator component without complex imports.
"""

import sys
import os
import asyncio
import pytest
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from security.validator import SecurityValidator, LibraryHealthStatus
from security.models import SecurityConfiguration, ValidationResult, SecurityViolation, SecuritySeverity, SecurityAction

class TestSecurityValidator:
    """Test suite for SecurityValidator component."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = SecurityConfiguration(
            max_query_length=4096,
            max_metadata_fields=50,
            max_context_tokens=8192,
            max_tokens=1000,
            injection_detection_threshold=0.8,
            sanitization_confidence_threshold=0.7
        )
        self.validator = SecurityValidator(self.config)
    
    def test_initialization(self):
        """Test SecurityValidator initialization."""
        assert self.validator.config is not None
        assert isinstance(self.validator.library_health, LibraryHealthStatus)
        assert len(self.validator._compiled_patterns) == len(SecurityValidator.HIGH_RISK_PATTERNS)
    
    def test_library_status_summary(self):
        """Test library status summary generation."""
        summary = self.validator._get_library_status_summary()
        assert isinstance(summary, str)
        assert "libinjection:" in summary
        assert "bleach:" in summary
        assert "markupsafe:" in summary
    
    @pytest.mark.asyncio
    async def test_input_length_validation_within_limit(self):
        """Test input length validation for inputs within the limit."""
        test_input = "a" * 1024  # 1KB, within 4KB limit
        context = {"source_ip": "127.0.0.1"}
        
        result = await self.validator.validate_input(test_input, context)
        
        # Should not have length violations
        length_violations = [v for v in result.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations) == 0
    
    @pytest.mark.asyncio
    async def test_input_length_validation_exceeds_limit(self):
        """Test input length validation for inputs exceeding MAX_REQUEST_SIZE."""
        test_input = "a" * 5000  # 5KB, exceeds 4KB limit
        context = {"source_ip": "127.0.0.1"}
        
        result = await self.validator.validate_input(test_input, context)
        
        # Should have length violation
        length_violations = [v for v in result.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations) == 1
        assert length_violations[0].severity == SecuritySeverity.ERROR
        assert length_violations[0].confidence_score == 1.0
        assert "4096 bytes" in length_violations[0].description
    
    @pytest.mark.asyncio
    async def test_input_length_boundary_conditions(self):
        """Test boundary conditions for input length validation."""
        context = {"source_ip": "127.0.0.1"}
        
        # Test exactly at limit (4096 bytes)
        test_input_at_limit = "a" * 4096
        result_at_limit = await self.validator.validate_input(test_input_at_limit, context)
        length_violations_at_limit = [v for v in result_at_limit.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations_at_limit) == 0
        
        # Test one byte over limit (4097 bytes)
        test_input_over_limit = "a" * 4097
        result_over_limit = await self.validator.validate_input(test_input_over_limit, context)
        length_violations_over_limit = [v for v in result_over_limit.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations_over_limit) == 1
    
    @pytest.mark.asyncio
    async def test_fallback_pattern_detection(self):
        """Test fallback pattern detection for high-risk patterns."""
        test_cases = [
            ("<script>alert('xss')</script>", "script_tag_injection"),
            ("'; DROP TABLE users; --", "sql_drop_injection"),
            ("$(document).ready(function(){});", "jquery_injection"),
            ("{{user.name}}", "template_injection"),
            ("`rm -rf /`", "backtick_injection"),
            ("test\x00null", "null_byte_injection"),
            ("javascript:alert('xss')", "javascript_protocol"),
            ("data:text/html,<script>alert(1)</script>", "data_uri_html"),
            ("vbscript:msgbox('xss')", "vbscript_protocol"),
            ("<img onload='alert(1)'>", "event_handler_injection"),
            ("<img onerror='alert(1)'>", "event_handler_injection"),
            ("eval('malicious code')", "eval_injection"),
            ("document.cookie = 'stolen'", "cookie_access"),
            ("window.location = 'evil.com'", "location_manipulation"),
        ]
        
        context = {"source_ip": "127.0.0.1"}
        
        for test_input, expected_pattern in test_cases:
            result = await self.validator.validate_input(test_input, context)
            
            # Check for fallback pattern violations
            fallback_violations = [
                v for v in result.violations 
                if v.violation_type.startswith("fallback_") and expected_pattern in v.violation_type
            ]
            
            assert len(fallback_violations) > 0, f"Expected fallback pattern '{expected_pattern}' not detected in '{test_input}'"
            assert fallback_violations[0].confidence_score > 0.0
            assert fallback_violations[0].detected_pattern is not None
    
    @pytest.mark.asyncio
    async def test_sanitization_basic(self):
        """Test basic input sanitization functionality."""
        test_input = "<script>alert('xss')</script>Hello World"
        
        result = await self.validator.sanitize_input(test_input)
        
        # Should remove or neutralize script tags
        assert "<script>" not in result
        assert "Hello World" in result or "Hello" in result
    
    @pytest.mark.asyncio
    async def test_query_parameter_validation(self):
        """Test query parameter validation against defined limits."""
        # Test valid parameters
        valid_params = {
            "metadata": {"key1": "value1", "key2": "value2"},
            "top_k": 10,
        }
        
        result = await self.validator.validate_query_parameters(valid_params)
        assert result.is_valid
        assert len(result.violations) == 0
        
        # Test metadata fields exceeding limit
        invalid_metadata = {"metadata": {f"key{i}": f"value{i}" for i in range(60)}}  # Exceeds 50
        result = await self.validator.validate_query_parameters(invalid_metadata)
        assert not result.is_valid
        metadata_violations = [v for v in result.violations if v.violation_type == "metadata_fields_exceeded"]
        assert len(metadata_violations) == 1
    
    def test_confidence_score_aggregation(self):
        """Test confidence score aggregation from multiple detection engines."""
        # Test with no scores (should return 1.0)
        assert self.validator._calculate_overall_confidence([]) == 1.0
        
        # Test with single score
        assert self.validator._calculate_overall_confidence([0.8]) == 0.8
        
        # Test with multiple scores (weighted average)
        scores = [0.9, 0.8, 0.7]
        result = self.validator._calculate_overall_confidence(scores)
        # Should be a weighted average favoring higher confidence scores
        assert 0.8 <= result <= 0.85
    
    def test_recommended_action_determination(self):
        """Test recommended action determination based on violations."""
        # No violations should return ALLOW
        assert self.validator._determine_recommended_action([]) == SecurityAction.ALLOW
        
        # Critical violations should return BLOCK
        critical_violation = SecurityViolation(
            violation_type="test",
            severity=SecuritySeverity.CRITICAL,
            description="Critical test violation",
            confidence_score=0.9
        )
        assert self.validator._determine_recommended_action([critical_violation]) == SecurityAction.BLOCK
        
        # High-confidence error violations should return BLOCK
        high_conf_error = SecurityViolation(
            violation_type="test",
            severity=SecuritySeverity.ERROR,
            description="High confidence error",
            confidence_score=0.95
        )
        assert self.validator._determine_recommended_action([high_conf_error]) == SecurityAction.BLOCK
        
        # XSS violations should return SANITIZE
        xss_violation = SecurityViolation(
            violation_type="xss_injection",
            severity=SecuritySeverity.WARNING,
            description="XSS test violation",
            confidence_score=0.8
        )
        assert self.validator._determine_recommended_action([xss_violation]) == SecurityAction.SANITIZE
    
    @pytest.mark.asyncio
    async def test_library_health_check(self):
        """Test library health monitoring functionality."""
        # Perform health check
        health_status = await self.validator.check_library_health()
        
        assert isinstance(health_status, LibraryHealthStatus)
        assert health_status.last_health_check is not None
        assert isinstance(health_status.health_check_errors, list)
        
        # Test library status retrieval
        status = self.validator.get_library_status()
        assert isinstance(status, dict)
        assert "libinjection" in status
        assert "bleach" in status
        assert "markupsafe" in status
        assert "pymodsecurity" in status
        assert "fallback_patterns_count" in status
        assert status["fallback_patterns_count"] == len(SecurityValidator.HIGH_RISK_PATTERNS)
    
    @pytest.mark.asyncio
    async def test_processing_time_measurement(self):
        """Test that processing time is measured and included in results."""
        test_input = "test input"
        context = {"source_ip": "127.0.0.1"}
        
        result = await self.validator.validate_input(test_input, context)
        
        assert result.processing_time_ms >= 0
        assert isinstance(result.processing_time_ms, float)
    
    @pytest.mark.asyncio
    async def test_comprehensive_integration_scenario(self):
        """Test comprehensive scenario with multiple detection engines."""
        # Input with multiple types of threats
        malicious_input = """
        <script>alert('xss')</script>
        '; DROP TABLE users; --
        javascript:alert('more xss')
        {{user.password}}
        eval('malicious code')
        """
        
        context = {
            "source_ip": "192.168.1.100",
            "user_agent": "Mozilla/5.0 (Test Browser)"
        }
        
        result = await self.validator.validate_input(malicious_input, context)
        
        # Should detect multiple violations
        assert not result.is_valid
        assert len(result.violations) > 0
        assert result.recommended_action in [SecurityAction.BLOCK, SecurityAction.SANITIZE]
        assert result.confidence_score > 0.0
        
        # Should have violations from fallback patterns at minimum
        fallback_violations = [v for v in result.violations if v.violation_type.startswith("fallback_")]
        assert len(fallback_violations) > 0
        
        # Test sanitization of the malicious input
        sanitized = await self.validator.sanitize_input(malicious_input)
        assert len(sanitized) < len(malicious_input)  # Should be shorter after sanitization
        assert "<script>" not in sanitized
        assert "javascript:" not in sanitized or "javascript-protocol-removed:" in sanitized


if __name__ == "__main__":
    # Run tests
    import subprocess
    result = subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"], 
                          capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    sys.exit(result.returncode)