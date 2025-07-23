"""Compatibility wrapper for the utils package.

This module simply aliases the legacy ``src.utils`` shim under the
``btc_max_knowledge_agent.utils`` import path so that both old and new import
statements resolve to the same runtime objects *without* introducing circular
import issues.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys
from pathlib import Path

# Ensure src directory is in the path
_project_root = Path(__file__).parent.parent.parent.parent
_src_path = str(_project_root / "src")
if _src_path not in _sys.path:
    _sys.path.insert(0, _src_path)

# Define the submodules we need to forward
_SUBMODULES = ["url_utils", "url_metadata_logger", "url_error_handler", "config", "result_formatter"]

# Forward each submodule individually
for _submodule in _SUBMODULES:
    try:
        # Try different import paths
        _sub_mod = None
        for import_path in [f"utils.{_submodule}", f"src.utils.{_submodule}"]:
            try:
                _sub_mod = _importlib.import_module(import_path)
                break
            except ImportError:
                continue
        
        if _sub_mod is None:
            raise ImportError(f"Could not import {_submodule} from any path")
            
        # Register the module under the new namespace
        _sys.modules[f"btc_max_knowledge_agent.utils.{_submodule}"] = _sub_mod
        # Also make it available as an attribute of this module
        globals()[_submodule] = _sub_mod
    except ImportError as e:
        # If a specific module fails to import, create a stub to prevent cascade failures
        import types
        _stub = types.ModuleType(f"btc_max_knowledge_agent.utils.{_submodule}")
        _sys.modules[f"btc_max_knowledge_agent.utils.{_submodule}"] = _stub
        globals()[_submodule] = _stub
        print(f"Warning: Could not import {_submodule}: {e}")

# Import the main utils module for backward compatibility
_utils_mod = None
for import_path in ["utils", "src.utils"]:
    try:
        _utils_mod = _importlib.import_module(import_path)
        break
    except ImportError:
        continue

if _utils_mod:
    # Export everything from the shim at this namespace
    for _attr in dir(_utils_mod):
        if not _attr.startswith('_'):
            globals()[_attr] = getattr(_utils_mod, _attr)
