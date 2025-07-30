#!/usr/bin/env python3
"""
Test utilities for robust import handling and common test functionality.
"""

import sys
from pathlib import Path
from typing import Optional


def setup_test_imports() -> bool:
    """
    Set up imports for test files in a robust way.
    
    This function handles the common pattern of adding the src directory
    to the Python path for testing, but does it in a more robust way
    than direct sys.path manipulation.
    
    Returns:
        bool: True if setup was successful, False otherwise
    """
    try:
        # Get the project root directory (where this file is located)
        project_root = Path(__file__).parent.absolute()
        src_dir = project_root / 'src'
        
        # Validate that the source directory exists
        if not src_dir.exists():
            print(f"❌ Source directory not found: {src_dir}")
            return False
        
        # Only add to path if not already present
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)
            
        return True
        
    except Exception as e:
        print(f"❌ Error setting up test imports: {e}")
        return False


def validate_security_imports() -> bool:
    """
    Validate that security modules can be imported successfully.
    
    Returns:
        bool: True if all imports successful, False otherwise
    """
    try:
        # Test core security imports
        from security.validator import SecurityValidator, LibraryHealthStatus
        from security.models import (
            SecurityConfiguration, 
            ValidationResult, 
            SecurityViolation, 
            SecuritySeverity, 
            SecurityAction
        )
        from security.config import SecurityConfigurationManager
        from security.interfaces import ISecurityValidator
        
        return True
        
    except ImportError as e:
        print(f"❌ Security module import failed: {e}")
        print("   Make sure the security infrastructure is properly implemented.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during import validation: {e}")
        return False


def get_test_config() -> Optional['SecurityConfiguration']:
    """
    Get a standard test configuration for security tests.
    
    Returns:
        SecurityConfiguration or None if import fails
    """
    try:
        from security.models import SecurityConfiguration
        
        return SecurityConfiguration(
            max_query_length=4096,
            max_metadata_fields=50,
            max_context_tokens=8192,
            max_tokens=1000,
            injection_detection_threshold=0.8,
            sanitization_confidence_threshold=0.7
        )
    except ImportError:
        return None


def print_test_header(test_name: str, description: str = ""):
    """Print a formatted test header."""
    print(f"\n🔒 {test_name}")
    print("=" * 50)
    if description:
        print(f"{description}\n")


def print_test_summary(passed: int, total: int, test_name: str = "Tests"):
    """Print a formatted test summary."""
    print("\n" + "=" * 50)
    print(f"🎯 {test_name} Results: {passed}/{total} passed")
    
    if passed == total:
        print(f"🎉 All tests passed! {test_name} implementation is working correctly.")
    else:
        failed = total - passed
        print(f"❌ {failed} test{'s' if failed != 1 else ''} failed.")


class TestAssertion:
    """Helper class for test assertions with automatic counting."""
    
    def __init__(self):
        self.test_count = 0
        self.passed_count = 0
    
    def assert_test(self, condition: bool, message: str) -> bool:
        """
        Assert a test condition and track results.
        
        Args:
            condition: The condition to test
            message: Description of what is being tested
            
        Returns:
            bool: The condition result
        """
        self.test_count += 1
        if condition:
            self.passed_count += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        return condition
    
    def get_results(self) -> tuple[int, int]:
        """Get (passed, total) test counts."""
        return self.passed_count, self.test_count
    
    def print_summary(self, test_name: str = "Tests"):
        """Print test summary."""
        print_test_summary(self.passed_count, self.test_count, test_name)
        
    def all_passed(self) -> bool:
        """Check if all tests passed."""
        return self.passed_count == self.test_count


# Example usage function
def example_test_setup():
    """
    Example of how to use the test utilities.
    This can be used as a template for other test files.
    """
    # Set up imports
    if not setup_test_imports():
        sys.exit(1)
    
    # Validate security imports
    if not validate_security_imports():
        sys.exit(1)
    
    # Get test configuration
    config = get_test_config()
    if config is None:
        print("❌ Failed to create test configuration")
        sys.exit(1)
    
    # Print test header
    print_test_header("Example Test", "This is an example test setup")
    
    # Create test assertion helper
    test = TestAssertion()
    
    # Run some example tests
    test.assert_test(config is not None, "Configuration created successfully")
    test.assert_test(config.max_query_length == 4096, "Configuration has correct max_query_length")
    
    # Print summary
    test.print_summary("Example Tests")
    
    return test.all_passed()


if __name__ == "__main__":
    # Run example if called directly
    success = example_test_setup()
    sys.exit(0 if success else 1)