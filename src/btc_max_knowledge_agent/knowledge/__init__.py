"""
Knowledge collection and management for the Bitcoin Max Knowledge Agent.

This package includes components for collecting, processing, and managing
Bitcoin-related knowledge from various sources.

This subpackage exposes the `BitcoinDataCollector` class. During the
package-layout transition, the actual implementation still lives in the
legacy `knowledge.data_collector` module that sits outside the packaged
namespace.  To avoid a massive file move while tests are refactored, we
import the implementation dynamically and re-export it here.
"""

import importlib
from types import ModuleType
from typing import TYPE_CHECKING

# Dynamically import the legacy implementation that still resides in the
# repository at `src/knowledge/data_collector.py`.
_legacy_dc_mod: ModuleType = importlib.import_module("knowledge.data_collector")
BitcoinDataCollector = getattr(_legacy_dc_mod, "BitcoinDataCollector")
# Backward-compatibility alias
DataCollector = BitcoinDataCollector

if TYPE_CHECKING:  # pragma: no cover
    # Provide a static type for linters / IDEs.
    from knowledge.data_collector import BitcoinDataCollector  # noqa: F401

__all__ = [
    "BitcoinDataCollector",
]

__all__ = ["BitcoinDataCollector"]
