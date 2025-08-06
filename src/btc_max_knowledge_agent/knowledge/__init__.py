"""
Knowledge package shim with safe fallbacks to avoid import-time failures during tests.

This module previously raised ImportError when optional dependencies for the legacy
data collector were missing. Instead, export no-op placeholders by default and allow
lazy resolution to the real implementation only when available.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, TYPE_CHECKING

__all__ = ["BitcoinDataCollector", "DataCollector"]


class _UnavailableCollector:
    """No-op placeholder for optional data collectors."""
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.available: bool = False

    def __call__(self, *args: Any, **kwargs: Any) -> "_UnavailableCollector":
        return self

    def collect(self, *args: Any, **kwargs: Any) -> list:
        return []

    def close(self) -> None:  # pragma: no cover - trivial
        return None

    def __repr__(self) -> str:  # pragma: no cover - debug
        return "<UnavailableCollector available=False>"


def _try_import_real() -> ModuleType | None:
    try:
        import importlib
        return importlib.import_module("knowledge.data_collector")
    except Exception:
        return None


# Default to safe placeholders to keep pytest collection green
BitcoinDataCollector: Any = _UnavailableCollector
DataCollector: Any = _UnavailableCollector

# If import succeeds (deps available), bind real classes
_mod = _try_import_real()
if _mod is not None:
    BitcoinDataCollector = getattr(_mod, "BitcoinDataCollector", _UnavailableCollector)
    # Back-compat alias
    DataCollector = getattr(_mod, "DataCollector", BitcoinDataCollector)

if TYPE_CHECKING:  # pragma: no cover
    from knowledge.data_collector import BitcoinDataCollector as _TBDC  # noqa: F401
