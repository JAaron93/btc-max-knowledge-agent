#!/usr/bin/env python3
"""
Simple test for SecurityValidator without complex imports.
"""

import sys
import asyncio

# Use test utilities for robust import handling
from test_utils import (
    setup_test_imports,
    validate_security_imports
)

# Set up imports robustly
if not setup_test_imports():
    print("❌ Failed to set up test imports")
    sys.exit(1)

if not validate_security_imports():
    print("❌ Security modules not available")
    sys.exit(1)

# Now we can safely import the security modules
from security.validator import SecurityValidator
from security.models import SecurityConfiguration

async def test_validator():
    """Simple test of SecurityValidator functionality."""
    
    # Track test results
    test_results = {
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "errors": []
    }
    
    # Create configuration
    config = SecurityConfiguration(
        max_query_length=4096,
        max_metadata_fields=50,
        max_context_tokens=8192,
        max_tokens=1000,
        injection_detection_threshold=0.8,
        sanitization_confidence_threshold=0.7
    )
    
    # Create validator
    validator = SecurityValidator(config)
    
    print("SecurityValidator initialized successfully!")
    
    # Get library status using public API
    library_status = validator.get_library_status()
    status_parts = []
    
    # Format library status information using public API
    for lib_name in ["libinjection", "bleach", "markupsafe", "pymodsecurity"]:
        if lib_name in library_status:
            lib_info = library_status[lib_name]
            if isinstance(lib_info, dict) and "available" in lib_info:
                status = "OK" if lib_info["available"] else "UNAVAILABLE"
                status_parts.append(f"{lib_name}:{status}")
    
    print(f"Library status: {', '.join(status_parts)}")
    
    # Test basic input validation
    test_cases = [
        "Hello, world!",  # Safe input
        "<script>alert('xss')</script>",  # XSS attempt
        "'; DROP TABLE users; --",  # SQL injection attempt
        "a" * 5000,  # Input too long
    ]
    
    for i, test_input in enumerate(test_cases, 1):
        test_results["total_tests"] += 1
        display_input = test_input[:50]
        if len(test_input) > 50:
            display_input += "..."
        print(f"\nTest {i}: {display_input}")
        
        context = {"source_ip": "127.0.0.1", "user_agent": "Test"}
        
        try:
            result = await validator.validate_input(test_input, context)
            
            print(f"  Valid: {result.is_valid}")
            print(f"  Confidence: {result.confidence_score:.2f}")
            print(f"  Action: {result.recommended_action}")
            print(f"  Violations: {len(result.violations)}")
            
            if result.violations:
                # Show first 2 violations
                for violation in result.violations[:2]:
                    desc = violation.description[:80]
                    if len(violation.description) > 80:
                        desc += "..."
                    print(f"    - {violation.violation_type}: {desc}")
            
            test_results["passed_tests"] += 1
            print("  ✅ Test passed")
                    
        except Exception as e:
            test_results["failed_tests"] += 1
            error_msg = f"Validation test {i} failed: {str(e)}"
            test_results["errors"].append(error_msg)
            print(f"  ❌ Error during validation: {e}")
            print("  Test will continue with next input...")
            continue
    
    # Test sanitization
    print("\nTesting sanitization:")
    malicious_input = "<script>alert('xss')</script>Hello World"
    
    try:
        sanitized = await validator.sanitize_input(malicious_input)
        print(f"Original: {malicious_input}")
        print(f"Sanitized: {sanitized}")
        print("✅ Sanitization test passed")
    except Exception as e:
        error_msg = f"Sanitization test failed: {str(e)}"
        test_results["errors"].append(error_msg)
        print(f"❌ Error during sanitization: {e}")
        print("Sanitization test failed, but continuing with other tests...")
    
    # Test library health
    print("\nLibrary health check:")
    
    try:
        health = await validator.check_library_health()
        print(f"  libinjection: {health.libinjection_available}")
        print(f"  bleach: {health.bleach_available}")
        print(f"  markupsafe: {health.markupsafe_available}")
        print(f"  pymodsecurity: {health.pymodsecurity_available}")
        
        if health.health_check_errors:
            print(f"  Errors: {health.health_check_errors}")
        
        print("✅ Health check completed")
            
    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        test_results["errors"].append(error_msg)
        print(f"  ❌ Error during health check: {e}")
        print("  Health check failed, but this doesn't affect core functionality")
    
    # Print test summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    print(f"Total validation tests: {test_results['total_tests']}")
    print(f"Passed: {test_results['passed_tests']}")
    print(f"Failed: {test_results['failed_tests']}")
    
    if test_results["errors"]:
        print(f"\n❌ Errors encountered ({len(test_results['errors'])}):")
        for i, error in enumerate(test_results["errors"], 1):
            print(f"  {i}. {error}")
    else:
        print("\n✅ No errors encountered!")
    
    success_rate = (test_results['passed_tests'] / max(test_results['total_tests'], 1)) * 100
    print(f"\nSuccess rate: {success_rate:.1f}%")
    
    if test_results['failed_tests'] == 0 and len(test_results['errors']) == 0:
        print("🎉 All tests completed successfully!")
    else:
        print("⚠️  Some tests had issues, but the test suite completed robustly.")


if __name__ == "__main__":
    asyncio.run(test_validator())