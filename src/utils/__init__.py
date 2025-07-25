"""src.utils shim

This module provides a backward-compatibility bridge for legacy imports such as
``import src.utils.url_utils`` or ``from src.utils import url_metadata_logger``.

During the migration to the new namespaced package
`btc_max_knowledge_agent.utils`, we leave the original ``src`` directory in
place but forward sub-module look-ups to their modern counterparts whenever
possible.  This keeps existing tests and third-party code working without
needing to update every import statement immediately.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from types import ModuleType
from typing import Any

# from btc_max_knowledge_agent.utils.url_error_handler import query_retry_with_backoff

# ---------------------------------------------------------------------------
# Ensure a *src* top-level module exists and that *src.utils* refers to this
# shim *before* any other import attempts occur.  This is critical because
# ``btc_max_knowledge_agent.utils`` imports legacy paths like
# ``src.utils.url_utils`` during its own initialisation.
# ---------------------------------------------------------------------------
_parent = sys.modules.setdefault("src", types.ModuleType("src"))

# Make sure the parent package behaves like a namespace package with a valid
# ``__path__`` so the import machinery can traverse into sub-packages.
if not hasattr(_parent, "__path__"):
    _parent.__path__ = []  # type: ignore[attr-defined]

_current_dir = str(Path(__file__).resolve().parent)
if _current_dir not in _parent.__path__:
    _parent.__path__.append(_current_dir)  # type: ignore[attr-defined]

# Bind this module instance as the *utils* attribute and in *sys.modules* so
# that both ``import src.utils`` and attribute access work interchangeably.
setattr(_parent, "utils", sys.modules[__name__])
sys.modules.setdefault("src.utils", sys.modules[__name__])
# Register this shim as the canonical implementation for the *new* package
# namespace as well so that ``import btc_max_knowledge_agent.utils`` resolves
# to the same module instance.
sys.modules.setdefault("btc_max_knowledge_agent.utils", sys.modules[__name__])

# Sub-modules that have a 1-to-1 replacement inside the new namespaced package.
_FWD_SUBMODULES = (
    "url_utils",
    "url_metadata_logger",
    "url_error_handler",
    "config",
    "result_formatter",
    "audio_cache",
)


def _forward(submodule: str) -> ModuleType:  # pragma: no cover
    """Dynamically import and register a forwarded sub-module.

    If the corresponding module exists under
    ``btc_max_knowledge_agent.utils.<submodule>``, import it and register the
    result under both ``src.utils.<submodule>`` and the standard dotted path so
    that subsequent imports resolve to the same object.
    """
    try:
        # Prefer local legacy implementation to avoid circular imports.
        target = importlib.import_module(f"{__name__}.{submodule}")
    except ModuleNotFoundError:
        # Fall back to the new packaged namespace if the local module does not exist.
        target = importlib.import_module(f"btc_max_knowledge_agent.utils.{submodule}")

    # Ensure *both* import paths reference the same module instance.
    sys.modules[f"{__name__}.{submodule}"] = target
    # Also register under the new package namespace so that
    # ``btc_max_knowledge_agent.utils.<submodule>`` resolves.
    sys.modules.setdefault(f"btc_max_knowledge_agent.utils.{submodule}", target)
    return target


def __getattr__(name: str) -> Any:  # noqa: D401
    """Lazy attribute access for *unknown* sub-modules.

    This hook is triggered when an attribute is requested that hasn't been
    defined yet (e.g. ``src.utils.some_new_module``).  We attempt to resolve it
    via the forwarding mechanism and cache the result for future look-ups.
    """
    return _forward(name)


__all__ = list(_FWD_SUBMODULES)
