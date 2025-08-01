"""
Test utilities for robust module importing and path management.

This module provides utilities to handle imports from the src directory
in a robust way that works across different environments and test runners.

USAGE:
    Instead of fragile sys.path manipulation like:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    
    Use the robust approach:
        from test_utils import setup_src_path
        setup_src_path()

BENEFITS:
    • Cross-platform compatibility with pathlib
    • Absolute path resolution prevents issues
    • Duplicate path checking avoids sys.path pollution
    • Centralized utility for consistency across tests
    • Better error handling and debugging capabilities
"""

import os
import sys
import warnings
from pathlib import Path
from typing import Optional


def setup_src_path() -> Path:
    """
    Add the src directory to Python path for importing project modules.
    
    This function uses pathlib for robust path resolution and only adds
    the src directory if it's not already in the path.
    
    Returns:
        Path object pointing to the src directory

    Raises:
        FileNotFoundError: If the src directory does not exist
    """
    # Get the absolute path to the src directory
    src_dir = Path(__file__).parent.parent / "src"
    src_dir = src_dir.resolve()  # Convert to absolute path

    # Validate that the src directory exists
    if not src_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")
    
    # Only add to path if not already present
    src_str = str(src_dir)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    
    return src_dir


def is_module_available(module_name: str) -> bool:
    """
    Check if a module from src is available for import.
    
    This function checks module availability without guaranteeing it will be available
    after the call. It first attempts to import the module, and if that fails,
    sets up the src path and retries the import once.
    
    Args:
        module_name: Name of the module to check (e.g., 'security.models')
        
    Returns:
        True if module is available for import, False otherwise
    """
    # First attempt: try importing the module directly
    try:
        __import__(module_name)
        return True
    except ImportError:
        pass  # Continue to retry with src path setup
    
    # Second attempt: set up src path and try importing again
    try:
        setup_src_path()
        __import__(module_name)
        return True
    except ImportError:
        return False


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    Returns:
        Path object pointing to the project root
    """
    return Path(__file__).parent.parent


def get_src_dir() -> Path:
    """
    Get the src directory path.
    
    Returns:
        Path object pointing to the src directory
    """
    return get_project_root() / "src"


def get_tests_dir() -> Path:
    """
    Get the tests directory path.
    
    Returns:
        Path object pointing to the tests directory
    """
    return get_project_root() / "tests"


# Automatically set up src path when this module is imported
# This can be controlled via environment variable or will fail gracefully if src directory is missing
def _auto_setup_src_path() -> None:
    """
    Automatically set up src path with error handling and optional control.
    
    This function is called on module import to set up the src path. It includes:
    - Error handling to prevent import failures if src directory is missing
    - Optional control via TEST_UTILS_AUTO_SETUP environment variable
    - Graceful degradation if setup fails
    """
    # Check if auto setup is disabled via environment variable
    if os.getenv('TEST_UTILS_AUTO_SETUP', '1').lower() in ('0', 'false', 'no', 'off'):
        return
    
    # Attempt to set up src path with error handling
    try:
        setup_src_path()
    except FileNotFoundError as e:
        # Src directory doesn't exist - this is not necessarily an error
        # as the module might be used in contexts where src isn't available
        pass
    except Exception as e:
        # Other unexpected errors - log but don't fail the import
        warnings.warn(
            f"Failed to automatically set up src path: {e}. "
            f"You may need to call setup_src_path() manually or set TEST_UTILS_AUTO_SETUP=0 "
            f"to disable automatic setup.",
            ImportWarning
        )

# Perform automatic setup
_auto_setup_src_path()