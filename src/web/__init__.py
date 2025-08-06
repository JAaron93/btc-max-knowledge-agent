"""
Web package re-exports for test imports.

We intentionally expose specific symbols to stabilize import surfaces expected
by the test suite. Flake8 unused-import warnings are suppressed via __all__.
"""

from .session_manager import SessionData, SessionManager, get_session_manager

__all__ = [
    "SessionData",
    "SessionManager",
    "get_session_manager",
]
