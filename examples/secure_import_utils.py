#!/usr/bin/env python3
"""
Secure Import Utilities for Example Scripts

This module provides secure import functionality that avoids sys.path manipulation
and prevents potential security risks from path injection attacks.
"""

import importlib.util
from pathlib import Path
from typing import Any, Optional


def safe_import_from_project(
    module_path: str, module_name: Optional[str] = None
) -> Any:
    """
    Safely import a module from the project without modifying sys.path.

    This approach is more secure than sys.path manipulation because:
    - It doesn't globally modify the Python path
    - It uses explicit path resolution
    - It prevents potential security issues from path injection
    - It's more predictable and doesn't affect other imports

    Args:
        module_path: Relative path to the module from project root (e.g., 'src/web/admin_auth.py')
        module_name: Optional module name for the spec (defaults to derived name)

    Returns:
        The imported module

    Raises:
        ImportError: If the module cannot be found or loaded
    """
    try:
        project_root = Path(__file__).parent.parent.resolve()
        full_module_path = project_root / module_path

        if not full_module_path.exists():
            raise ImportError(f"Module not found: {full_module_path}")

        if module_name is None:
            module_name = module_path.replace("/", ".").replace(".py", "")

        spec = importlib.util.spec_from_file_location(module_name, full_module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec for {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    except Exception as e:
        raise ImportError(f"Failed to safely import {module_path}: {e}") from e


def import_class_from_project(
    module_path: str, class_name: str, module_name: Optional[str] = None
) -> type:
    """
    Safely import a specific class from a project module.

    Args:
        module_path: Relative path to the module from project root
        class_name: Name of the class to import
        module_name: Optional module name for the spec

    Returns:
        The imported class

    Raises:
        ImportError: If the module or class cannot be found
    """
    module = safe_import_from_project(module_path, module_name)

    if not hasattr(module, class_name):
        raise ImportError(f"Class '{class_name}' not found in module {module_path}")

    return getattr(module, class_name)
