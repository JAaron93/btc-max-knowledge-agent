#!/usr/bin/env python3
"""
Direct unit tests for SecurityValidator component.
"""

import sys
import os
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from security.validator import SecurityValidator, LibraryHealthStatus
from security.models import SecurityConfiguration, ValidationResult, SecurityViolation, SecuritySeverity, SecurityAction

async def run_tests():
    """Run all SecurityValidator tests."""
    
    print("🔒 SecurityValidator Unit Tests")
    print("=" * 50)
    
    # Setup
    config = SecurityConfiguration(
        max_query_length=4096,
        max_metadata_fields=50,
        max_context_tokens=8192,
        max_tokens=1000,
        injection_detection_threshold=0.8,
        sanitization_confidence_threshold=0.7
    )
    validator = SecurityValidator(config)
    
    test_count = 0
    passed_count = 0
    
    def test_assert(condition, message):
        nonlocal test_count, passed_count
        test_count += 1
        if condition:
            passed_count += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
    
    # Test 1: Initialization
    test_assert(validator.config is not None, "SecurityValidator initialization")
    test_assert(isinstance(validator.library_health, LibraryHealthStatus), "Library health status initialization")
    test_assert(len(validator._compiled_patterns) == len(SecurityValidator.HIGH_RISK_PATTERNS), "Pattern compilation")
    
    # Test 2: Library status summary
    summary = validator._get_library_status_summary()
    test_assert(isinstance(summary, str), "Library status summary generation")
    test_assert("libinjection:" in summary, "Library status includes libinjection")
    test_assert("bleach:" in summary, "Library status includes bleach")
    
    # Test 3: Input length validation - within limit
    test_input = "a" * 1024  # 1KB
    context = {"source_ip": "127.0.0.1"}
    result = await validator.validate_input(test_input, context)
    length_violations = [v for v in result.violations if v.violation_type == "input_length_exceeded"]
    test_assert(len(length_violations) == 0, "Input within length limit passes validation")
    
    # Test 4: Input length validation - exceeds limit
    test_input = "a" * 5000  # 5KB, exceeds 4KB limit
    result = await validator.validate_input(test_input, context)
    length_violations = [v for v in result.violations if v.violation_type == "input_length_exceeded"]
    test_assert(len(length_violations) == 1, "Input exceeding length limit fails validation")
    test_assert(length_violations[0].severity == SecuritySeverity.ERROR, "Length violation has ERROR severity")
    test_assert(length_violations[0].confidence_score == 1.0, "Length violation has high confidence")
    
    # Test 5: Boundary conditions
    test_input_at_limit = "a" * 4096  # Exactly at limit
    result_at_limit = await validator.validate_input(test_input_at_limit, context)
    length_violations_at_limit = [v for v in result_at_limit.violations if v.violation_type == "input_length_exceeded"]
    test_assert(len(length_violations_at_limit) == 0, "Input exactly at limit passes validation")
    
    test_input_over_limit = "a" * 4097  # One byte over
    result_over_limit = await validator.validate_input(test_input_over_limit, context)
    length_violations_over_limit = [v for v in result_over_limit.violations if v.violation_type == "input_length_exceeded"]
    test_assert(len(length_violations_over_limit) == 1, "Input one byte over limit fails validation")
    
    # Test 6: Fallback pattern detection
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
        ("eval('malicious code')", "eval_injection"),
        ("document.cookie = 'stolen'", "cookie_access"),
        ("window.location = 'evil.com'", "location_manipulation"),
    ]
    
    for test_input, expected_pattern in test_cases:
        result = await validator.validate_input(test_input, context)
        fallback_violations = [
            v for v in result.violations 
            if v.violation_type.startswith("fallback_") and expected_pattern in v.violation_type
        ]
        test_assert(len(fallback_violations) > 0, f"Fallback pattern detection: {expected_pattern}")
        if fallback_violations:
            test_assert(fallback_violations[0].confidence_score > 0.0, f"Confidence score for {expected_pattern}")
            test_assert(fallback_violations[0].detected_pattern is not None, f"Detected pattern for {expected_pattern}")
    
    # Test 7: Sanitization
    test_input = "<script>alert('xss')</script>Hello World"
    sanitized = await validator.sanitize_input(test_input)
    test_assert("<script>" not in sanitized, "Script tags removed during sanitization")
    test_assert("Hello" in sanitized, "Safe content preserved during sanitization")
    
    # Test 8: Query parameter validation
    valid_params = {"metadata": {"key1": "value1", "key2": "value2"}}
    result = await validator.validate_query_parameters(valid_params)
    test_assert(result.is_valid, "Valid query parameters pass validation")
    test_assert(len(result.violations) == 0, "Valid query parameters have no violations")
    
    invalid_metadata = {"metadata": {f"key{i}": f"value{i}" for i in range(60)}}  # Exceeds 50
    result = await validator.validate_query_parameters(invalid_metadata)
    test_assert(not result.is_valid, "Invalid query parameters fail validation")
    metadata_violations = [v for v in result.violations if v.violation_type == "metadata_fields_exceeded"]
    test_assert(len(metadata_violations) == 1, "Metadata field limit violation detected")
    
    # Test 9: Confidence score aggregation
    test_assert(validator._calculate_overall_confidence([]) == 1.0, "Empty confidence scores return 1.0")
    test_assert(validator._calculate_overall_confidence([0.8]) == 0.8, "Single confidence score preserved")
    
    scores = [0.9, 0.8, 0.7]
    result = validator._calculate_overall_confidence(scores)
    test_assert(0.8 <= result <= 0.85, "Multiple confidence scores aggregated correctly")
    
    # Test 10: Recommended action determination
    test_assert(validator._determine_recommended_action([]) == SecurityAction.ALLOW, "No violations allow action")
    
    critical_violation = SecurityViolation(
        violation_type="test", severity=SecuritySeverity.CRITICAL, 
        description="Critical test violation", confidence_score=0.9
    )
    test_assert(validator._determine_recommended_action([critical_violation]) == SecurityAction.BLOCK, 
                "Critical violations block action")
    
    high_conf_error = SecurityViolation(
        violation_type="test", severity=SecuritySeverity.ERROR, 
        description="High confidence error", confidence_score=0.95
    )
    test_assert(validator._determine_recommended_action([high_conf_error]) == SecurityAction.BLOCK, 
                "High confidence errors block action")
    
    xss_violation = SecurityViolation(
        violation_type="xss_injection", severity=SecuritySeverity.WARNING, 
        description="XSS test violation", confidence_score=0.8
    )
    test_assert(validator._determine_recommended_action([xss_violation]) == SecurityAction.SANITIZE, 
                "XSS violations sanitize action")
    
    # Test 11: Library health check
    health_status = await validator.check_library_health()
    test_assert(isinstance(health_status, LibraryHealthStatus), "Library health check returns correct type")
    test_assert(health_status.last_health_check is not None, "Health check timestamp recorded")
    test_assert(isinstance(health_status.health_check_errors, list), "Health check errors is list")
    
    status = validator.get_library_status()
    test_assert(isinstance(status, dict), "Library status returns dictionary")
    test_assert("libinjection" in status, "Library status includes libinjection")
    test_assert("bleach" in status, "Library status includes bleach")
    test_assert("markupsafe" in status, "Library status includes markupsafe")
    test_assert("fallback_patterns_count" in status, "Library status includes pattern count")
    test_assert(status["fallback_patterns_count"] == len(SecurityValidator.HIGH_RISK_PATTERNS), 
                "Pattern count matches HIGH_RISK_PATTERNS")
    
    # Test 12: Processing time measurement
    test_input = "test input"
    result = await validator.validate_input(test_input, context)
    test_assert(result.processing_time_ms >= 0, "Processing time is non-negative")
    test_assert(isinstance(result.processing_time_ms, float), "Processing time is float")
    
    # Test 13: Comprehensive integration scenario
    malicious_input = """
    <script>alert('xss')</script>
    '; DROP TABLE users; --
    javascript:alert('more xss')
    {{user.password}}
    eval('malicious code')
    """
    
    context = {"source_ip": "192.168.1.100", "user_agent": "Mozilla/5.0 (Test Browser)"}
    result = await validator.validate_input(malicious_input, context)
    
    test_assert(not result.is_valid, "Malicious input fails validation")
    test_assert(len(result.violations) > 0, "Malicious input has violations")
    test_assert(result.recommended_action in [SecurityAction.BLOCK, SecurityAction.SANITIZE], 
                "Malicious input has appropriate action")
    test_assert(result.confidence_score > 0.0, "Malicious input has confidence score")
    
    fallback_violations = [v for v in result.violations if v.violation_type.startswith("fallback_")]
    test_assert(len(fallback_violations) > 0, "Malicious input detected by fallback patterns")
    
    sanitized = await validator.sanitize_input(malicious_input)
    test_assert(len(sanitized) < len(malicious_input), "Sanitization reduces input size")
    test_assert("<script>" not in sanitized, "Script tags removed by sanitization")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed_count}/{test_count} passed")
    
    if passed_count == test_count:
        print("🎉 All tests passed! SecurityValidator implementation is working correctly.")
        return True
    else:
        print(f"❌ {test_count - passed_count} tests failed.")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)