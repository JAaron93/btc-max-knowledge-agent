#!/usr/bin/env python3
"""
Legacy shim: Delegate tests to canonical module in tests/unit/utils.

Important: To avoid pytest's import file mismatch, mark this file to be
ignored by pytest collection while keeping it for backward compatibility.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="legacy forwarder; use tests/unit/utils/test_utils.py")