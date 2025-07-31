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

import sys
from pathlib import Path
from typing import Optional


def setup_src_path() -> Path:
    """
    Add the src directory to Python path for importing project modules.
    
    This function uses pathlib for robust path resolution and only adds
    the src directory if it's not already in the path.
    
    Returns:
        Path object pointing to the src directory
    """
    # Get the absolute path to the src directory
    src_dir = Path(__file__).parent.parent / "src"
    src_dir = src_dir.resolve()  # Convert to absolute path
    
    # Only add to path if not already present
    src_str = str(src_dir)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    
    return src_dir


def ensure_module_available(module_name: str) -> bool:
    """
    Ensure a module from src is available for import.
    
    Args:
        module_name: Name of the module to check (e.g., 'security.models')
        
    Returns:
        True if module is available, False otherwise
    """
    try:
        __import__(module_name)
        return True
    except ImportError:
        # Try setting up src path and importing again
        setup_src_path()
        try:
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
setup_src_path()