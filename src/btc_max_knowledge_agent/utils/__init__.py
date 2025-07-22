"""Compatibility wrapper for the utils package.

This module simply aliases the legacy ``src.utils`` shim under the
``btc_max_knowledge_agent.utils`` import path so that both old and new import
statements resolve to the same runtime objects *without* introducing circular
import issues.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

# Import (or create) the legacy shim package.
_utils_mod = _importlib.import_module("src.utils")

# Export everything from the shim at this namespace.
globals().update(_utils_mod.__dict__)

# Ensure that both names map to the *same* module instance.
_sys.modules[__name__] = _utils_mod
