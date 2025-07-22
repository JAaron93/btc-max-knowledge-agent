"""Package-forwarding shim for BitcoinDataCollector.

This thin wrapper allows importing
`btc_max_knowledge_agent.knowledge.data_collector` while the implementation
still resides in the legacy `knowledge.data_collector` module outside of the
packaged namespace.
"""

from importlib import import_module

# Re-export everything from the legacy module.
_legacy = import_module("knowledge.data_collector")

# Expose the primary class under the expected name.
BitcoinDataCollector = _legacy.BitcoinDataCollector  # type: ignore[attr-defined]
DataCollector = BitcoinDataCollector  # convenience alias

# Re-export public attributes of the legacy module to behave transparently.
__all__ = [name for name in dir(_legacy) if not name.startswith("_")]
for _name in __all__:
    globals()[_name] = getattr(_legacy, _name)
