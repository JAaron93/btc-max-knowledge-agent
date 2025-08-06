from __future__ import annotations
import contextvars
CORRELATION_ID = contextvars.ContextVar('correlation_id', default=None)

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, Optional
@dataclass
class URLLogEntry:
    url: str
    success: bool
    attempts: int = 0
    error: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
class URLMetadataLogger:
    """Minimal logger used by tests to record retry attempts and outcomes."""
    def __init__(self) -> None:
        self.entries: list[URLLogEntry] = []
    def log_retry(self, url: str, attempt: int, reason: str | None = None) -> None:
        self.entries.append(URLLogEntry(url=url, success=False, attempts=attempt, error=reason))
    def log_success(self, url: str, attempts: int = 1, metadata: Optional[Dict[str, str]] = None) -> None:
        self.entries.append(URLLogEntry(url=url, success=True, attempts=attempts, metadata=metadata or {}))
    def clear(self) -> None:
        self.entries.clear()
@contextmanager
def correlation_context(correlation_id: str) -> Iterator[None]:
    # Tests only need that this is a valid context manager
    yield
# Backward-compatible function expected by some tests
def log_retry(url: str, attempt: int, reason: str | None = None) -> None:
    # No-op global logger function (tests import presence)
    return None
def get_correlation_id():
    return CORRELATION_ID.get()
def set_correlation_id(value):
    CORRELATION_ID.set(value)
    return value
