#!/usr/bin/env python3
"""
SessionManager: Thread-safe, in-memory session management
for FastAPI-backed services with TTL expiration support.

Provides simple CRUD operations on in-memory sessions with basic metadata and
expiry handling. Designed to satisfy imports from security.prompt_processor.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List, Callable


@dataclass
class SessionData:
    """Compatibility dataclass representing session metadata for tests."""
    session_id: str
    created_at: float
    last_accessed_at: float
    ttl_seconds: Optional[int]
    data: Dict[str, Any]

# Default TTL for sessions (1 hour) to centralize configuration
DEFAULT_SESSION_TTL_SECONDS = 3600

@dataclass
class Session:
    """Lightweight session container."""
    session_id: str
    created_at: float = field(default_factory=lambda: time.time())
    last_accessed_at: float = field(default_factory=lambda: time.time())
    data: Dict[str, Any] = field(default_factory=dict)
    # Optional expiry seconds; if 0 or None, session does not
    # expire automatically
    ttl_seconds: Optional[int] = DEFAULT_SESSION_TTL_SECONDS  # default 1 hour

    def touch(self) -> None:
        self.last_accessed_at = time.time()

    def is_expired(self, now: Optional[float] = None) -> bool:
        if not self.ttl_seconds:
            return False
        now = now or time.time()
        return (now - self.last_accessed_at) > self.ttl_seconds


class SessionManager:
    """
    Thread-safe in-memory session manager with minimal API surface.

    Methods:
      - create_session(session_id, **kwargs) -> Session
      - get_session(session_id) -> Optional[Session]
      - update_session(session_id, **data) -> bool
      - remove_session(session_id) -> bool
      - end_session(session_id) -> bool (alias of remove_session)
      - list_sessions(skip=0, limit=100) -> List[Dict[str, Any]]
      - get_session_stats() -> Dict[str, Any]
      - cleanup_expired_sessions() -> int
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.RLock()

    # Creation and retrieval

    def create_session(
        self,
        session_id: str,
        *,
        ttl_seconds: Optional[int] = None,
        **data: Any,
    ) -> Session:
        with self._lock:
            sess = Session(
                session_id=session_id,
                ttl_seconds=(
                    ttl_seconds
                    if ttl_seconds is not None
                    else Session.ttl_seconds
                ),
                data=dict(data) if data else {},
            )
            self._sessions[session_id] = sess
            return sess

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return None
            if sess.is_expired():
                # Lazy cleanup on access
                del self._sessions[session_id]
                return None
            sess.touch()
            return sess

    # Update and removal

    def update_session(self, session_id: str, **data: Any) -> bool:
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return False
            if sess.is_expired():
                del self._sessions[session_id]
                return False
            if data:
                sess.data.update(data)
            sess.touch()
            return True

    def remove_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    # Semantic alias used by some code/tests
    def end_session(self, session_id: str) -> bool:
        return self.remove_session(session_id)

    # Introspection and maintenance

    def list_sessions(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            now = time.time()
            session_items: List[Tuple[str, Session]] = list(
                self._sessions.items()
            )
            # Eagerly filter expired and cleanup
            alive: List[Tuple[str, Session]] = []
            for sid, sess in session_items:
                if sess.is_expired(now):
                    del self._sessions[sid]
                    continue
                alive.append((sid, sess))

            # Apply pagination after cleanup
            # Python slicing handles negative and out-of-bounds indices gracefully.
            sliced = alive[skip: skip + limit]
            return [
                {
                    "session_id": sid,
                    "created_at": sess.created_at,
                    "last_accessed_at": sess.last_accessed_at,
                    "ttl_seconds": sess.ttl_seconds,
                    "data_keys": list(sess.data.keys()),
                }
                for sid, sess in sliced
            ]

    def get_session_stats(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            total = 0
            active = 0
            expired = 0
            ages: List[float] = []
            for sid, sess in list(self._sessions.items()):
                total += 1
                if sess.is_expired(now):
                    expired += 1
                    # Lazy cleanup is fine; explicit cleanup provided by
                    # cleanup_expired_sessions
                    continue
                active += 1
                ages.append(now - sess.created_at)

            oldest_age = max(ages) if ages else 0.0
            newest_age = min(ages) if ages else 0.0
            avg_age = (sum(ages) / len(ages)) if ages else 0.0

            return {
                "total_sessions": total,
                "active_sessions": active,
                "expired_sessions_detected": expired,
                "oldest_session_age_seconds": round(oldest_age, 3),
                "newest_session_age_seconds": round(newest_age, 3),
                "average_session_age_seconds": round(avg_age, 3),
                "timestamp": now,
            }

    def cleanup_expired_sessions(self) -> int:
        with self._lock:
            now = time.time()
            to_delete = [
                sid
                for sid, sess in self._sessions.items()
                if sess.is_expired(now)
            ]
            for sid in to_delete:
                del self._sessions[sid]
            return len(to_delete)


# Simple module-level singleton accessor expected by tests
_default_session_manager: Optional[SessionManager] = None
_default_session_manager_factory: Optional[Callable[[], SessionManager]] = None


def reset_session_manager() -> None:
    """
    Reset the module-level singleton so tests can recreate a fresh instance.

    This avoids test cross-contamination when different factories are desired.
    """
    global _default_session_manager, _default_session_manager_factory
    _default_session_manager = None
    _default_session_manager_factory = None


def get_session_manager(factory: Optional[Callable[[], SessionManager]] = None) -> SessionManager:
    """
    Return a singleton SessionManager instance.

    Behavior:
      - If no instance exists, create one using the provided factory (if any) or the default SessionManager.
      - If an instance exists and a new factory is provided (different from the last one),
        replace the singleton with a new instance created by that factory to honor test isolation.
      - Tests that need full control can also call reset_session_manager() explicitly.
    """
    global _default_session_manager, _default_session_manager_factory

    # If we already have an instance but caller provides a (different) factory,
    # recreate the singleton to ensure isolation for tests using different setups.
    if _default_session_manager is not None and factory is not None:
        if _default_session_manager_factory is None or factory is not _default_session_manager_factory:
            _default_session_manager = factory()
            _default_session_manager_factory = factory
            return _default_session_manager

    if _default_session_manager is None:
        if factory:
            _default_session_manager = factory()
            _default_session_manager_factory = factory
        else:
            _default_session_manager = SessionManager()
            _default_session_manager_factory = None

    return _default_session_manager


__all__ = [
    "SessionData",
    "Session",
    "SessionManager",
    "get_session_manager",
]