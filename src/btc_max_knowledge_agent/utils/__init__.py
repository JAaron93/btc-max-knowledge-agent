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
_current_file = Path(__file__).resolve()
# Walk up to find project root (containing src directory)
_project_root = _current_file.parent
while _project_root.parent != _project_root:
    if (_project_root / "src").is_dir():
        break
    _project_root = _project_root.parent
else:
    raise ImportError("Could not find project root with 'src' directory")

_src_path = str(_project_root / "src")
if _src_path not in _sys.path:
    _sys.path.insert(0, _src_path)

# Define the submodules we need to forward
_SUBMODULES = [
    "url_utils", "url_metadata_logger", "url_error_handler",
    "config", "result_formatter", "audio_utils"
]

# Explicitly define what is exported to prevent namespace pollution
__all__ = _SUBMODULES.copy()

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
        # Log the error but don't create stubs that will cause AttributeError
        # later
        import warnings
        warnings.warn(
            f"Could not import {_submodule}: {e}. "
            f"This module will not be available.",
            ImportWarning,
            stacklevel=2
        )

# Try to import the main utils module to forward any additional attributes
_utils_mod = None
for import_path in ["utils", "src.utils"]:
    try:
        _utils_mod = _importlib.import_module(import_path)
        break
    except ImportError:
        continue

if _utils_mod:
    # Export everything from the shim at this namespace
    _exported_attrs = []
    for _attr in dir(_utils_mod):
        if not _attr.startswith('_') and _attr not in globals():
            globals()[_attr] = getattr(_utils_mod, _attr)
            _exported_attrs.append(_attr)

    # Update __all__ to include the exported attributes
    __all__.extend(_exported_attrs)
else:
    import warnings
    warnings.warn(
        "Could not import main utils module. "
        "Only submodules will be available.",
        ImportWarning,
        stacklevel=2
    )
