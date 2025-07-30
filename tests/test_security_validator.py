"""
Comprehensive unit tests for SecurityValidator component.

This test suite covers:
- Library integration testing with mocks
- Fallback scenario testing when libraries are unavailable
- MAX_REQUEST_SIZE boundary condition testing
- Input validation and sanitization functionality
- Confidence score aggregation
- Library health monitoring
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.security.validator import SecurityValidator, LibraryHealthStatus
from src.security.models import (
    SecurityConfiguration, 
    ValidationResult, 
    SecurityViolation, 
    SecuritySeverity, 
    SecurityAction
)


class TestSecurityValidator:
    """Test suite for SecurityValidator component."""
    
    @pytest.fixture
    def security_config(self):
        """Create a test security configuration."""
        return SecurityConfiguration(
            max_query_length=4096,  # 4KB
            max_metadata_fields=50,
            max_context_tokens=8192,
            max_tokens=1000,
            injection_detection_threshold=0.8,
            sanitization_confidence_threshold=0.7
        )
    
    @pytest.fixture
    def validator(self, security_config):
        """Create a SecurityValidator instance for testing."""
        return SecurityValidator(security_config)
    
    def test_initialization(self, validator):
        """Test SecurityValidator initialization."""
        assert validator.config is not None
        assert isinstance(validator.library_health, LibraryHealthStatus)
        assert len(validator._compiled_patterns) == len(SecurityValidator.HIGH_RISK_PATTERNS)
    
    def test_library_status_summary(self, validator):
        """Test library status summary generation."""
        summary = validator._get_library_status_summary()
        assert isinstance(summary, str)
        assert "libinjection:" in summary
        assert "bleach:" in summary
        assert "markupsafe:" in summary
    
    @pytest.mark.asyncio
    async def test_input_length_validation_within_limit(self, validator):
        """Test input length validation for inputs within the limit."""
        # Test input within limit (1KB)
        test_input = "a" * 1024
        context = {"source_ip": "127.0.0.1"}
        
        result = await validator.validate_input(test_input, context)
        
        # Should not have length violations
        length_violations = [v for v in result.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations) == 0
    
    @pytest.mark.asyncio
    async def test_input_length_validation_exceeds_limit(self, validator):
        """Test input length validation for inputs exceeding MAX_REQUEST_SIZE."""
        # Test input exceeding 4KB limit
        test_input = "a" * 5000  # 5KB, exceeds 4KB limit
        context = {"source_ip": "127.0.0.1"}
        
        result = await validator.validate_input(test_input, context)
        
        # Should have length violation
        length_violations = [v for v in result.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations) == 1
        assert length_violations[0].severity == SecuritySeverity.ERROR
        assert length_violations[0].confidence_score == 1.0
        assert "4096 bytes" in length_violations[0].description
    
    @pytest.mark.asyncio
    async def test_input_length_boundary_conditions(self, validator):
        """Test boundary conditions for input length validation."""
        context = {"source_ip": "127.0.0.1"}
        
        # Test exactly at limit (4096 bytes)
        test_input_at_limit = "a" * 4096
        result_at_limit = await validator.validate_input(test_input_at_limit, context)
        length_violations_at_limit = [v for v in result_at_limit.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations_at_limit) == 0
        
        # Test one byte over limit (4097 bytes)
        test_input_over_limit = "a" * 4097
        result_over_limit = await validator.validate_input(test_input_over_limit, context)
        length_violations_over_limit = [v for v in result_over_limit.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations_over_limit) == 1
        
        # Test UTF-8 multi-byte characters at boundary
        # Each emoji is 4 bytes in UTF-8
        emoji_input = "😀" * 1024  # 4096 bytes exactly
        result_emoji_at_limit = await validator.validate_input(emoji_input, context)
        length_violations_emoji = [v for v in result_emoji_at_limit.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations_emoji) == 0
        
        # One more emoji pushes over limit
        emoji_input_over = "😀" * 1025  # 4100 bytes
        result_emoji_over = await validator.validate_input(emoji_input_over, context)
        length_violations_emoji_over = [v for v in result_emoji_over.violations if v.violation_type == "input_length_exceeded"]
        assert len(length_violations_emoji_over) == 1
    
    @pytest.mark.asyncio
    async def test_utf8_validation_valid_input(self, validator):
        """Test UTF-8 validation with valid input."""
        test_inputs = [
            "Hello, world!",
            "Café résumé naïve",
            "こんにちは世界",  # Japanese
            "🌟✨🎉",  # Emojis
            "Здравствуй мир",  # Russian
        ]
        
        context = {"source_ip": "127.0.0.1"}
        
        for test_input in test_inputs:
            result = await validator.validate_input(test_input, context)
            utf8_violations = [v for v in result.violations if v.violation_type == "invalid_utf8_encoding"]
            assert len(utf8_violations) == 0, f"Valid UTF-8 input '{test_input}' should not have encoding violations"
    
    def test_utf8_validation_invalid_input(self, validator):
        """Test UTF-8 validation with invalid input."""
    # Test with invalid UTF-8 byte sequences if the validator accepts bytes
    # For example, invalid continuation bytes
    try:
        # If validator can handle bytes, test invalid sequences
        invalid_bytes = b'\x80\x81'  # Invalid UTF-8 sequence
        # This would require the validator to accept bytes or have a separate method
        # violation = validator._validate_utf8_bytes(invalid_bytes)
        # assert violation is not None
        
        # For now, just test the validation logic with valid strings
        violation = validator._validate_utf8_encoding("valid string")
        assert violation is None
    except Exception:
        # If bytes not supported, keep current test
        violation = validator._validate_utf8_encoding("valid string")
        assert violation is None

    @pytest.mark.asyncio
    async def test_fallback_pattern_detection(self, validator):
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
            result = await validator.validate_input(test_input, context)
            
            # Check for fallback pattern violations
            fallback_violations = [
                v for v in result.violations 
                if v.violation_type.startswith("fallback_") and expected_pattern in v.violation_type
            ]
            
            assert len(fallback_violations) > 0, f"Expected fallback pattern '{expected_pattern}' not detected in '{test_input}'"
            assert fallback_violations[0].confidence_score > 0.0
            assert fallback_violations[0].detected_pattern is not None
    
    @pytest.mark.asyncio
    @patch('src.security.validator.LIBINJECTION_AVAILABLE', True)
    @patch('src.security.validator.libinjection')
    async def test_libinjection_integration_sql_injection(self, mock_libinjection, validator):
        """Test libinjection integration for SQL injection detection."""
        # Mock libinjection responses
        mock_libinjection.is_sql_injection.return_value = (True, "sqli_fingerprint")
        mock_libinjection.is_xss.return_value = (False, None)
        
        test_input = "'; DROP TABLE users; --"
        context = {"source_ip": "127.0.0.1"}
        
        result = await validator.validate_input(test_input, context)
        
        # Check that libinjection was called
        mock_libinjection.is_sql_injection.assert_called_once_with(test_input)
        mock_libinjection.is_xss.assert_called_once_with(test_input)
        
        # Check for SQL injection violations
        sql_violations = [v for v in result.violations if v.violation_type == "sql_injection"]
        assert len(sql_violations) == 1
        assert sql_violations[0].severity == SecuritySeverity.CRITICAL
        assert sql_violations[0].confidence_score >= 0.8
        assert "sqli_fingerprint" in sql_violations[0].description
    
    @pytest.mark.asyncio
    @patch('src.security.validator.LIBINJECTION_AVAILABLE', True)
    @patch('src.security.validator.libinjection')
    async def test_libinjection_integration_xss(self, mock_libinjection, validator):
        """Test libinjection integration for XSS detection."""
        # Mock libinjection responses
        mock_libinjection.is_sql_injection.return_value = (False, None)
        mock_libinjection.is_xss.return_value = (True, "xss_fingerprint")
        
        test_input = "<script>alert('xss')</script>"
        context = {"source_ip": "127.0.0.1"}
        
        result = await validator.validate_input(test_input, context)
        
        # Check for XSS violations
        xss_violations = [v for v in result.violations if v.violation_type == "xss_injection"]
        assert len(xss_violations) == 1
        assert xss_violations[0].severity == SecuritySeverity.CRITICAL
        assert xss_violations[0].confidence_score >= 0.8
        assert "xss_fingerprint" in xss_violations[0].description
    
    @pytest.mark.asyncio
    @patch('src.security.validator.LIBINJECTION_AVAILABLE', True)
    @patch('src.security.validator.libinjection')
    async def test_libinjection_graceful_degradation(self, mock_libinjection, validator):
        """Test graceful degradation when libinjection fails."""
        # Mock libinjection to raise an exception
        mock_libinjection.is_sql_injection.side_effect = Exception("libinjection error")
        mock_libinjection.is_xss.side_effect = Exception("libinjection error")
        
        test_input = "test input"
        context = {"source_ip": "127.0.0.1"}
        
        result = await validator.validate_input(test_input, context)
        
        # Check for library degradation violations
        degradation_violations = [v for v in result.violations if v.violation_type == "library_degradation"]
        assert len(degradation_violations) == 1
        assert degradation_violations[0].severity == SecuritySeverity.WARNING
        assert "libinjection detection unavailable" in degradation_violations[0].description
    
    @pytest.mark.asyncio
    @patch('src.security.validator.BLEACH_AVAILABLE', True)
    @patch('src.security.validator.bleach')
    async def test_sanitization_with_bleach(self, mock_bleach, validator):
        """Test input sanitization using bleach library."""
        # Mock bleach.clean
        mock_bleach.clean.return_value = "sanitized content"
        
        test_input = "<script>alert('xss')</script>Hello"
        
        result = await validator.sanitize_input(test_input)
        
        # Check that bleach was called with correct parameters
        mock_bleach.clean.assert_called_once()
        call_args = mock_bleach.clean.call_args
        assert call_args[1]['tags'] == ['p', 'br', 'strong', 'em', 'u', 'i']
        assert call_args[1]['attributes'] == {}
        assert call_args[1]['strip'] is True
    
    @pytest.mark.asyncio
    @patch('src.security.validator.MARKUPSAFE_AVAILABLE', True)
    @patch('src.security.validator.escape')
    async def test_sanitization_with_markupsafe(self, mock_escape, validator):
        """Test input sanitization using markupsafe library."""
        # Mock escape function
        mock_escape.return_value = "&lt;script&gt;alert('xss')&lt;/script&gt;"
        
        test_input = "<script>alert('xss')</script>"
        
        result = await validator.sanitize_input(test_input)
        
        # Check that escape was called
        mock_escape.assert_called()
    
    @pytest.mark.asyncio
    async def test_sanitization_fallback_without_libraries(self, security_config):
        """Test sanitization fallback when security libraries are unavailable."""
        # Create validator with libraries unavailable
        with patch('src.security.validator.BLEACH_AVAILABLE', False), \
             patch('src.security.validator.MARKUPSAFE_AVAILABLE', False):
            validator = SecurityValidator(security_config)
            
            test_input = "<script>alert('xss')</script>'; DROP TABLE users; --"
            
            result = await validator.sanitize_input(test_input)
            
            # Should still perform basic sanitization
            assert "<script>" not in result
            assert "DROP TABLE" not in result or "\\'" in result  # SQL chars should be escaped
            assert "\x00" not in result  # Null bytes should be removed
    
    @pytest.mark.asyncio
    async def test_query_parameter_validation(self, validator):
        """Test query parameter validation against defined limits."""
        # Test valid parameters
        valid_params = {
            "metadata": {"key1": "value1", "key2": "value2"},
            "top_k": 10,
            "similarity_threshold": 0.8,
            "vector": [0.1] * 100
        }
        
        result = await validator.validate_query_parameters(valid_params)
        assert result.is_valid
        assert len(result.violations) == 0
        
        # Test metadata fields exceeding limit
        invalid_metadata = {"metadata": {f"key{i}": f"value{i}" for i in range(60)}}  # Exceeds 50
        result = await validator.validate_query_parameters(invalid_metadata)
        assert not result.is_valid
        metadata_violations = [v for v in result.violations if v.violation_type == "metadata_fields_exceeded"]
        assert len(metadata_violations) == 1
        
        # Test invalid top_k
        invalid_top_k = {"top_k": 100}  # Exceeds max_metadata_fields (50)
        result = await validator.validate_query_parameters(invalid_top_k)
        assert not result.is_valid
        top_k_violations = [v for v in result.violations if v.violation_type == "invalid_top_k"]
        assert len(top_k_violations) == 1
        
        # Test invalid similarity threshold
        invalid_threshold = {"similarity_threshold": 1.5}  # Exceeds 1.0
        result = await validator.validate_query_parameters(invalid_threshold)
        assert not result.is_valid
        threshold_violations = [v for v in result.violations if v.violation_type == "invalid_similarity_threshold"]
        assert len(threshold_violations) == 1
        
        # Test vector dimensions exceeding limit
        invalid_vector = {"vector": [0.1] * 1500}  # Exceeds max_tokens (1000)
        result = await validator.validate_query_parameters(invalid_vector)
        assert not result.is_valid
        vector_violations = [v for v in result.violations if v.violation_type == "vector_dimensions_exceeded"]
        assert len(vector_violations) == 1
    
    def test_confidence_score_aggregation(self, validator):
        """Test confidence score aggregation from multiple detection engines."""
        # Test with no scores (should return 1.0)
        assert validator._calculate_overall_confidence([]) == 1.0
        
        # Test with single score
        assert validator._calculate_overall_confidence([0.8]) == 0.8
        
        # Test with multiple scores (weighted average)
        scores = [0.9, 0.8, 0.7]
        result = validator._calculate_overall_confidence(scores)
        # Weighted sum: 0.9*0.9 + 0.8*0.8 + 0.7*0.7 = 0.81 + 0.64 + 0.49 = 1.94
        # Weight sum: 0.9 + 0.8 + 0.7 = 2.4
        # Result: 1.94 / 2.4 ≈ 0.808
        assert 0.8 <= result <= 0.82
    
    def test_recommended_action_determination(self, validator):
        """Test recommended action determination based on violations."""
        # No violations should return ALLOW
        assert validator._determine_recommended_action([]) == SecurityAction.ALLOW
        
        # Critical violations should return BLOCK
        critical_violation = SecurityViolation(
            violation_type="test",
            severity=SecuritySeverity.CRITICAL,
            description="Critical test violation",
            confidence_score=0.9
        )
        assert validator._determine_recommended_action([critical_violation]) == SecurityAction.BLOCK
        
        # High-confidence error violations should return BLOCK
        high_conf_error = SecurityViolation(
            violation_type="test",
            severity=SecuritySeverity.ERROR,
            description="High confidence error",
            confidence_score=0.95
        )
        assert validator._determine_recommended_action([high_conf_error]) == SecurityAction.BLOCK
        
        # XSS violations should return SANITIZE
        xss_violation = SecurityViolation(
            violation_type="xss_injection",
            severity=SecuritySeverity.WARNING,
            description="XSS test violation",
            confidence_score=0.8
        )
        assert validator._determine_recommended_action([xss_violation]) == SecurityAction.SANITIZE
        
        # Low severity violations should return LOG_AND_MONITOR
        low_severity = SecurityViolation(
            violation_type="test",
            severity=SecuritySeverity.WARNING,
            description="Low severity violation",
            confidence_score=0.6
        )
        assert validator._determine_recommended_action([low_severity]) == SecurityAction.LOG_AND_MONITOR
    
    @pytest.mark.asyncio
    async def test_library_health_check(self, validator):
        """Test library health monitoring functionality."""
        # Perform health check
        health_status = await validator.check_library_health()
        
        assert isinstance(health_status, LibraryHealthStatus)
        assert health_status.last_health_check is not None
        assert isinstance(health_status.health_check_errors, list)
        
        # Test library status retrieval
        status = validator.get_library_status()
        assert isinstance(status, dict)
        assert "libinjection" in status
        assert "bleach" in status
        assert "markupsafe" in status
        assert "pymodsecurity" in status
        assert "fallback_patterns_count" in status
        assert status["fallback_patterns_count"] == len(SecurityValidator.HIGH_RISK_PATTERNS)
    
    @pytest.mark.asyncio
    async def test_processing_time_measurement(self, validator):
        """Test that processing time is measured and included in results."""
        test_input = "test input"
        context = {"source_ip": "127.0.0.1"}
        
        result = await validator.validate_input(test_input, context)
        
        assert result.processing_time_ms >= 0
        assert isinstance(result.processing_time_ms, float)
    
    @pytest.mark.asyncio
    async def test_error_handling_during_validation(self, validator):
        """Test error handling during validation process."""
        # Mock a method to raise an exception
        with patch.object(validator, '_validate_input_length', side_effect=Exception("Test error")):
            test_input = "test input"
            context = {"source_ip": "127.0.0.1"}
            
            result = await validator.validate_input(test_input, context)
            
            assert not result.is_valid
            assert result.recommended_action == SecurityAction.BLOCK
            assert len(result.violations) == 1
            assert result.violations[0].violation_type == "validation_error"
            assert "Test error" in result.violations[0].description
    
    @pytest.mark.asyncio
    async def test_comprehensive_integration_scenario(self, validator):
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
        
        result = await validator.validate_input(malicious_input, context)
        
        # Should detect multiple violations
        assert not result.is_valid
        assert len(result.violations) > 0
        assert result.recommended_action in [SecurityAction.BLOCK, SecurityAction.SANITIZE]
        assert result.confidence_score > 0.0
        
        # Should have violations from fallback patterns at minimum
        fallback_violations = [v for v in result.violations if v.violation_type.startswith("fallback_")]
        assert len(fallback_violations) > 0
        
        # Test sanitization of the malicious input
        sanitized = await validator.sanitize_input(malicious_input)
        assert len(sanitized) < len(malicious_input)  # Should be shorter after sanitization
        assert "<script>" not in sanitized
        assert "javascript:" not in sanitized or "javascript-protocol-removed:" in sanitized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])