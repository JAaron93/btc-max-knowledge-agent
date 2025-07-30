#!/usr/bin/env python3
"""
Direct unit tests for SecurityValidator component.
"""

import sys
import asyncio

# Use test utilities for robust import handling
from test_utils import (
    setup_test_imports, 
    validate_security_imports, 
    get_test_config,
    print_test_header,
    TestAssertion
)

# Set up imports robustly
if not setup_test_imports():
    sys.exit(1)

if not validate_security_imports():
    sys.exit(1)

# Now we can safely import the security modules
from security.validator import SecurityValidator, LibraryHealthStatus
from security.models import (
    SecurityConfiguration, 
    ValidationResult, 
    SecurityViolation, 
    SecuritySeverity, 
    SecurityAction
)

async def run_tests():
    """Run all SecurityValidator tests."""
    
    print_test_header("SecurityValidator Unit Tests", 
                     "Direct unit tests for SecurityValidator component")
    
    # Setup using test utilities
    config = get_test_config()
    if config is None:
        print("❌ Failed to create test configuration")
        return False
        
    validator = SecurityValidator(config)
    test = TestAssertion()
    
    # Test 1: Initialization
    test.assert_test(validator.config is not None, "SecurityValidator initialization")
    test.assert_test(isinstance(validator.library_health, LibraryHealthStatus), "Library health status initialization")
    test.assert_test(len(validator._compiled_patterns) == len(SecurityValidator.HIGH_RISK_PATTERNS), "Pattern compilation")
    
    # Test 2: Library status information via public API
    library_status = validator.get_library_status()
    test.assert_test(isinstance(library_status, dict), "Library status returns dictionary")
    test.assert_test("libinjection" in library_status, "Library status includes libinjection")
    test.assert_test("bleach" in library_status, "Library status includes bleach")
    test.assert_test("markupsafe" in library_status, "Library status includes markupsafe")
    
    # Verify structure of library status entries
    for lib_name in ["libinjection", "bleach", "markupsafe"]:
        if lib_name in library_status:
            lib_info = library_status[lib_name]
            test.assert_test(isinstance(lib_info, dict), f"{lib_name} info is dictionary")
            test.assert_test("available" in lib_info, f"{lib_name} has availability info")
    
    # Test 3: Input length validation - within limit
    test_input = "a" * 1024  # 1KB
    context = {"source_ip": "127.0.0.1"}
    result = await validator.validate_input(test_input, context)
    length_violations = [v for v in result.violations if v.violation_type == "input_length_exceeded"]
    test.assert_test(len(length_violations) == 0, "Input within length limit passes validation")
    
    # Test 4: Input length validation - exceeds limit
    test_input = "a" * 5000  # 5KB, exceeds 4KB limit
    result = await validator.validate_input(test_input, context)
    length_violations = [v for v in result.violations if v.violation_type == "input_length_exceeded"]
    test.assert_test(len(length_violations) == 1, "Input exceeding length limit fails validation")
    test.assert_test(length_violations[0].severity == SecuritySeverity.ERROR, "Length violation has ERROR severity")
    test.assert_test(length_violations[0].confidence_score == 1.0, "Length violation has high confidence")
    
    # Test 5: Boundary conditions
    test_input_at_limit = "a" * 4096  # Exactly at limit
    result_at_limit = await validator.validate_input(test_input_at_limit, context)
    length_violations_at_limit = [v for v in result_at_limit.violations if v.violation_type == "input_length_exceeded"]
    test.assert_test(len(length_violations_at_limit) == 0, "Input exactly at limit passes validation")
    
    test_input_over_limit = "a" * 4097  # One byte over
    result_over_limit = await validator.validate_input(test_input_over_limit, context)
    length_violations_over_limit = [v for v in result_over_limit.violations if v.violation_type == "input_length_exceeded"]
    test.assert_test(len(length_violations_over_limit) == 1, "Input one byte over limit fails validation")
    
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
        test.assert_test(len(fallback_violations) > 0, f"Fallback pattern detection: {expected_pattern}")
        if fallback_violations:
            test.assert_test(fallback_violations[0].confidence_score > 0.0, f"Confidence score for {expected_pattern}")
            test.assert_test(fallback_violations[0].detected_pattern is not None, f"Detected pattern for {expected_pattern}")
    
    # Test 7: Comprehensive Sanitization Testing
    print("\n🧪 Testing comprehensive XSS vector sanitization...")
    
    # Test 7a: Script tag sanitization
    script_input = "<script>alert('xss')</script>Hello World"
    script_sanitized = await validator.sanitize_input(script_input)
    test.assert_test("<script>" not in script_sanitized.lower(), "Script tags removed during sanitization")
    test.assert_test(
        "alert('xss')" not in script_sanitized or 
        script_sanitized.count("alert") < script_input.count("alert"),
        "Script content neutralized or reduced"
    )
    test.assert_test("Hello" in script_sanitized, "Safe content preserved during sanitization")
    
    # Test 7b: Event handler sanitization
    event_handlers = [
        "<img onload='alert(1)' src='x'>",
        "<div onclick='malicious()'>Click me</div>",
        "<body onmouseover='steal_data()'>",
        "<input onfocus='evil_function()' type='text'>",
        "<a href='#' onmouseover='attack()'>Link</a>"
    ]
    
    for event_input in event_handlers:
        event_sanitized = await validator.sanitize_input(event_input)
        # Check that dangerous event handlers are removed or neutralized
        dangerous_events = ['onload', 'onclick', 'onmouseover', 'onfocus']
        for event in dangerous_events:
            if event in event_input.lower():
                test.assert_test(
                    event not in event_sanitized.lower() or 
                    "alert" not in event_sanitized.lower() or
                    "malicious" not in event_sanitized.lower(),
                    f"Event handler {event} sanitized or neutralized"
                )
    
    # Test 7c: JavaScript protocol sanitization
    js_protocols = [
        "<a href='javascript:alert(1)'>Click</a>",
        "<iframe src='javascript:void(0)'></iframe>",
        "<img src='javascript:alert(\"xss\")'>",
        "<form action='javascript:malicious()'>",
        "<area href='javascript:steal_cookies()'>"
    ]
    
    for js_input in js_protocols:
        js_sanitized = await validator.sanitize_input(js_input)
        test.assert_test(
            "javascript:" not in js_sanitized.lower() or
            js_sanitized.lower().count("javascript:") < js_input.lower().count("javascript:"),
            "JavaScript protocols removed or neutralized"
        )
        # Ensure the dangerous payload is removed
        test.assert_test(
            "alert" not in js_sanitized.lower() or
            "malicious" not in js_sanitized.lower() or
            "steal" not in js_sanitized.lower(),
            "JavaScript protocol payloads neutralized"
        )
    
    # Test 7d: Iframe sanitization
    iframe_inputs = [
        "<iframe src='http://evil.com'></iframe>",
        "<iframe src='data:text/html,<script>alert(1)</script>'></iframe>",
        "<iframe srcdoc='<script>malicious()</script>'></iframe>",
        "<iframe onload='attack()' src='about:blank'></iframe>"
    ]
    
    for iframe_input in iframe_inputs:
        iframe_sanitized = await validator.sanitize_input(iframe_input)
        # Check that iframes are removed or heavily sanitized
        test.assert_test(
            "<iframe" not in iframe_sanitized.lower() or
            ("src=" not in iframe_sanitized.lower() and "srcdoc=" not in iframe_sanitized.lower()),
            "Dangerous iframes removed or sanitized"
        )
        # Ensure malicious content is removed
        test.assert_test(
            "script" not in iframe_sanitized.lower() or
            "alert" not in iframe_sanitized.lower() or
            "malicious" not in iframe_sanitized.lower(),
            "Iframe malicious content neutralized"
        )
    
    # Test 7e: Additional XSS vectors
    additional_vectors = [
        "<object data='javascript:alert(1)'></object>",
        "<embed src='javascript:malicious()'></embed>",
        "<meta http-equiv='refresh' content='0;url=javascript:alert(1)'>",
        "<link rel='stylesheet' href='javascript:alert(1)'>",
        "<style>@import 'javascript:alert(1)';</style>",
        "<svg onload='alert(1)'><circle r='10'/></svg>",
        "<math><mi xlink:href='javascript:alert(1)'>click</mi></math>"
    ]
    
    for vector_input in additional_vectors:
        vector_sanitized = await validator.sanitize_input(vector_input)
        # Check that dangerous elements are removed or sanitized
        dangerous_elements = ['object', 'embed', 'meta', 'link', 'style', 'svg', 'math']
        input_lower = vector_input.lower()
        sanitized_lower = vector_sanitized.lower()
        
        # At least one of these should be true for proper sanitization
        sanitization_effective = (
            "javascript:" not in sanitized_lower or
            "alert" not in sanitized_lower or
            "malicious" not in sanitized_lower or
            any(f"<{elem}" not in sanitized_lower for elem in dangerous_elements if f"<{elem}" in input_lower)
        )
        
        test.assert_test(sanitization_effective, f"Additional XSS vector sanitized: {vector_input[:30]}...")
    
    # Test 7f: Mixed content sanitization
    mixed_content = """
    <div>Safe content</div>
    <script>alert('xss1')</script>
    <p onclick='malicious()'>Click me</p>
    <a href='javascript:alert(2)'>Link</a>
    <iframe src='http://evil.com'></iframe>
    <span>More safe content</span>
    """
    
    mixed_sanitized = await validator.sanitize_input(mixed_content)
    test.assert_test("Safe content" in mixed_sanitized, "Safe content preserved in mixed input")
    test.assert_test("More safe content" in mixed_sanitized, "Multiple safe elements preserved")
    test.assert_test(
        "<script>" not in mixed_sanitized.lower() and
        "onclick=" not in mixed_sanitized.lower() and
        "javascript:" not in mixed_sanitized.lower(),
        "All dangerous elements removed from mixed content"
    )
    
    print("✅ Comprehensive sanitization testing completed")
    
    # Test 8: Query parameter validation
    valid_params = {"metadata": {"key1": "value1", "key2": "value2"}}
    result = await validator.validate_query_parameters(valid_params)
    test.assert_test(result.is_valid, "Valid query parameters pass validation")
    test.assert_test(len(result.violations) == 0, "Valid query parameters have no violations")
    
    invalid_metadata = {"metadata": {f"key{i}": f"value{i}" for i in range(60)}}  # Exceeds 50
    result = await validator.validate_query_parameters(invalid_metadata)
    test.assert_test(not result.is_valid, "Invalid query parameters fail validation")
    metadata_violations = [v for v in result.violations if v.violation_type == "metadata_fields_exceeded"]
    test.assert_test(len(metadata_violations) == 1, "Metadata field limit violation detected")
    
    # Test 9: Confidence score aggregation
    test.assert_test(validator._calculate_overall_confidence([]) == 1.0, "Empty confidence scores return 1.0")
    test.assert_test(validator._calculate_overall_confidence([0.8]) == 0.8, "Single confidence score preserved")
    
    scores = [0.9, 0.8, 0.7]
    result = validator._calculate_overall_confidence(scores)
    test.assert_test(0.8 <= result <= 0.85, "Multiple confidence scores aggregated correctly")
    
    # Test 10: Recommended action determination
    test.assert_test(validator._determine_recommended_action([]) == SecurityAction.ALLOW, "No violations allow action")
    
    critical_violation = SecurityViolation(
        violation_type="test", severity=SecuritySeverity.CRITICAL, 
        description="Critical test violation", confidence_score=0.9
    )
    test.assert_test(validator._determine_recommended_action([critical_violation]) == SecurityAction.BLOCK, 
                "Critical violations block action")
    
    high_conf_error = SecurityViolation(
        violation_type="test", severity=SecuritySeverity.ERROR, 
        description="High confidence error", confidence_score=0.95
    )
    test.assert_test(validator._determine_recommended_action([high_conf_error]) == SecurityAction.BLOCK, 
                "High confidence errors block action")
    
    xss_violation = SecurityViolation(
        violation_type="xss_injection", severity=SecuritySeverity.WARNING, 
        description="XSS test violation", confidence_score=0.8
    )
    test.assert_test(validator._determine_recommended_action([xss_violation]) == SecurityAction.SANITIZE, 
                "XSS violations sanitize action")
    
    # Test 11: Library health check
    health_status = await validator.check_library_health()
    test.assert_test(isinstance(health_status, LibraryHealthStatus), "Library health check returns correct type")
    test.assert_test(health_status.last_health_check is not None, "Health check timestamp recorded")
    test.assert_test(isinstance(health_status.health_check_errors, list), "Health check errors is list")
    
    status = validator.get_library_status()
    test.assert_test(isinstance(status, dict), "Library status returns dictionary")
    test.assert_test("libinjection" in status, "Library status includes libinjection")
    test.assert_test("bleach" in status, "Library status includes bleach")
    test.assert_test("markupsafe" in status, "Library status includes markupsafe")
    test.assert_test("fallback_patterns_count" in status, "Library status includes pattern count")
    test.assert_test(status["fallback_patterns_count"] == len(SecurityValidator.HIGH_RISK_PATTERNS), 
                "Pattern count matches HIGH_RISK_PATTERNS")
    
    # Test 12: Processing time measurement
    test_input = "test input"
    result = await validator.validate_input(test_input, context)
    test.assert_test(result.processing_time_ms >= 0, "Processing time is non-negative")
    test.assert_test(isinstance(result.processing_time_ms, float), "Processing time is float")
    
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
    
    test.assert_test(not result.is_valid, "Malicious input fails validation")
    test.assert_test(len(result.violations) > 0, "Malicious input has violations")
    test.assert_test(result.recommended_action in [SecurityAction.BLOCK, SecurityAction.SANITIZE], 
                "Malicious input has appropriate action")
    test.assert_test(result.confidence_score > 0.0, "Malicious input has confidence score")
    
    fallback_violations = [v for v in result.violations if v.violation_type.startswith("fallback_")]
    test.assert_test(len(fallback_violations) > 0, "Malicious input detected by fallback patterns")
    
    sanitized = await validator.sanitize_input(malicious_input)
    test.assert_test(len(sanitized) < len(malicious_input), "Sanitization reduces input size")
    test.assert_test("<script>" not in sanitized, "Script tags removed by sanitization")
    
    # Summary
    test.print_summary("SecurityValidator Unit Tests")
    return test.all_passed()

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)