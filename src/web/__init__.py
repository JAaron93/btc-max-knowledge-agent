"""
Web package re-exports for test imports.

We intentionally expose specific symbols to stabilize the public import surface
used by the test suite. The __all__ list explicitly defines the public API.
"""

from .session_manager import SessionData, SessionManager, get_session_manager

__all__ = [
    "SessionData",
    "SessionManager",
    "get_session_manager",
]
