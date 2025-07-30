#!/usr/bin/env python3
"""
Simple test for SecurityValidator without complex imports.
"""

import sys
import os
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from security.validator import SecurityValidator
from security.models import SecurityConfiguration

async def test_validator():
    """Simple test of SecurityValidator functionality."""
    
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
    print(f"Library status: {validator._get_library_status_summary()}")
    
    # Test basic input validation
    test_cases = [
        "Hello, world!",  # Safe input
        "<script>alert('xss')</script>",  # XSS attempt
        "'; DROP TABLE users; --",  # SQL injection attempt
        "a" * 5000,  # Input too long
    ]
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_input[:50]}{'...' if len(test_input) > 50 else ''}")
        
        context = {"source_ip": "127.0.0.1", "user_agent": "Test"}
        result = await validator.validate_input(test_input, context)
        
        print(f"  Valid: {result.is_valid}")
        print(f"  Confidence: {result.confidence_score:.2f}")
        print(f"  Action: {result.recommended_action}")
        print(f"  Violations: {len(result.violations)}")
        
        if result.violations:
            for violation in result.violations[:2]:  # Show first 2 violations
                print(f"    - {violation.violation_type}: {violation.description[:80]}...")
    
    # Test sanitization
    print(f"\nTesting sanitization:")
    malicious_input = "<script>alert('xss')</script>Hello World"
    sanitized = await validator.sanitize_input(malicious_input)
    print(f"Original: {malicious_input}")
    print(f"Sanitized: {sanitized}")
    
    # Test library health
    health = await validator.check_library_health()
    print(f"\nLibrary health check:")
    print(f"  libinjection: {health.libinjection_available}")
    print(f"  bleach: {health.bleach_available}")
    print(f"  markupsafe: {health.markupsafe_available}")
    print(f"  pymodsecurity: {health.pymodsecurity_available}")
    
    if health.health_check_errors:
        print(f"  Errors: {health.health_check_errors}")
    
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_validator())