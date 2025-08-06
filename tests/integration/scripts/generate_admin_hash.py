#!/usr/bin/env python3
"""
Forwarder for integration tests to the canonical password hashing utility.

Keeps imports stable for legacy paths while maintaining a single source of truth
in tests/scripts/generate_admin_hash.py.
"""

from __future__ import annotations

from importlib import import_module as _im
from typing import Callable as _Callable, Any as _Any

_mod = _im("tests.scripts.generate_admin_hash")

hash_password: _Callable[..., str] = getattr(_mod, "hash_password")
verify_password: _Callable[..., bool] = getattr(_mod, "verify_password")

__all__ = ["hash_password", "verify_password"]