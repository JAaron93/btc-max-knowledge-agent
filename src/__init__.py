"""Legacy top-level `src` package.

This shim ensures that import statements like `from src.utils import ...`
continue to work during the transition to the packaged namespace
`btc_max_knowledge_agent`.

If a submodule has been migrated into the new package, we forward the import
to the new location. Otherwise, Python falls back to the actual legacy module
still living under the `src/` directory hierarchy.
"""

# Ensure this module is recognised as a namespace package.
import os
import sys
from importlib import import_module
from typing import List

# Ensure this behaves as a namespace package for importlib
__path__: List[str] = [os.path.dirname(__file__)]  # type: ignore[no-redef]

# Dynamically forward common subpackages to their new implementations.
_forward_subs = (
    "agents",
    "knowledge",
    "monitoring",
    "retrieval",
)

for _sub in _forward_subs:
    try:
        _target = import_module(f"btc_max_knowledge_agent.{_sub}")
        setattr(sys.modules[__name__], _sub, _target)
        sys.modules[f"{__name__}.{_sub}"] = _target
        # Make sure the forwarded subpackage is treated as a package
        if not hasattr(_target, "__path__"):
            _target.__path__ = []  # type: ignore[attr-defined]
        # Forward any child modules already imported
        prefix_old = f"btc_max_knowledge_agent.{_sub}."
        prefix_new = f"{__name__}.{_sub}."
        for mod_name, mod_obj in list(sys.modules.items()):
            if mod_name.startswith(prefix_old):
                forwarded_name = prefix_new + mod_name.removeprefix(prefix_old)
                sys.modules[forwarded_name] = mod_obj
    except ModuleNotFoundError:
        # If the module hasn't been migrated yet, simply ignore.
        continue
