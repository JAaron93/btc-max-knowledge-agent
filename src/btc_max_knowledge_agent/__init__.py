"""
Bitcoin Max Knowledge Agent - A knowledge management and retrieval system for Bitcoin information.

This package provides tools for collecting, processing, and retrieving Bitcoin-related knowledge
from various sources with robust error handling and monitoring.
"""

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Backward-compatibility alias
# ---------------------------------------------------------------------------
# Many existing modules still import from the legacy `src.<submodule>` path.
# Rather than refactor the entire codebase in one shot, we expose a dynamic
# alias so those imports continue to work while the transition to the new
# package layout is completed.
#
# Example: `from src.utils.config import Config` now resolves to
#          `btc_max_knowledge_agent.utils.config.Config`.

import importlib
import sys
import types

# ---------------------------------------------------------------------------
# Legacy `src` compatibility alias
# ---------------------------------------------------------------------------
# We try to import an actual `src` package first (for projects that still
# include the directory on disk). If that succeeds, we simply reference that
# package. Otherwise we manufacture a shim module and make sure it behaves
# like a proper namespace package with a non-empty `__path__` so that the
# import machinery does not raise KeyError while traversing parent paths.
from pathlib import Path

if "src" in sys.modules:
    # Re-use the existing package (either the real one on disk or a shim that
    # was already created by another import).
    _src_alias = sys.modules["src"]
else:
    # Create a lightweight shim so legacy `src.*` imports keep working.
    _src_alias = types.ModuleType("src")
    _legacy_src_path = Path(__file__).resolve().parent.parent / "src"
    _src_alias.__path__ = [str(_legacy_src_path)]  # type: ignore[attr-defined]
    sys.modules["src"] = _src_alias

# Ensure the alias behaves like a package for importlib machinery.
if not hasattr(_src_alias, "__path__"):
    _src_alias.__path__ = []  # type: ignore[attr-defined]
for _sub in (
    "utils",
    "agents",
    "knowledge",
    "monitoring",
    "retrieval",
):
    try:
        _mod = importlib.import_module(f"btc_max_knowledge_agent.{_sub}")
        setattr(_src_alias, _sub, _mod)
        sys.modules[f"src.{_sub}"] = _mod  # e.g. src.utils → utils package
    except ModuleNotFoundError:  # pragma: no cover
        # If a submodule hasn't been ported yet, skip it gracefully.
        continue

# Finally, register the top-level alias so `import src` works.
sys.modules["src"] = _src_alias
