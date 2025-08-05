#!/usr/bin/env python3
"""
Rate Limiter for API Endpoints
Provides protection against enumeration attacks and abuse
"""

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter with sliding window"""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter

        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.RLock()
        self._last_cleanup = time.time()

        logger.info(
            f"RateLimiter initialized: {max_requests} requests per {window_seconds}s"
        )

    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request is allowed for client

        Args:
            client_id: Unique identifier for client (IP, user ID, etc.)

        Returns:
            True if request is allowed, False if rate limited
        """
        current_time = time.time()

        with self._lock:
            # Cleanup old entries periodically
            if current_time - self._last_cleanup > 300:  # Every 5 minutes
                self._cleanup_old_entries(current_time)
                self._last_cleanup = current_time

            # Get request history for this client
            client_requests = self._requests[client_id]

            # Remove requests outside the window
            cutoff_time = current_time - self.window_seconds
            while client_requests and client_requests[0] < cutoff_time:
                client_requests.popleft()

            import hashlib

            # Remove requests outside the window
            cutoff_time = current_time - self.window_seconds
            while client_requests and client_requests[0] < cutoff_time:
                client_requests.popleft()

            if len(client_requests) < self.max_requests:
                client_requests.append(current_time)
                return True
            else:
                client_hash = hashlib.sha256(client_id.encode()).hexdigest()[:8]
                logger.warning(
                    f"Rate limit exceeded for client {client_hash}: "
                    f"{len(client_requests)} requests in {self.window_seconds}s"
                )
                return False
            if len(client_requests) < self.max_requests:
                client_requests.append(current_time)
                return True
            else:
                logger.warning(
                    f"Rate limit exceeded for client {client_id}: {len(client_requests)} requests in {self.window_seconds}s"
                )
                return False

    def _cleanup_old_entries(self, current_time: float):
        """Remove old entries to prevent memory leaks"""
        cutoff_time = current_time - (self.window_seconds * 2)  # Keep some buffer

        clients_to_remove = []
        for client_id, requests in self._requests.items():
            # Remove old requests
            while requests and requests[0] < cutoff_time:
                requests.popleft()

            # Remove empty client entries
            if not requests:
                clients_to_remove.append(client_id)

        for client_id in clients_to_remove:
            del self._requests[client_id]

        if clients_to_remove:
            logger.debug(f"Cleaned up {len(clients_to_remove)} inactive client entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        with self._lock:
            active_clients = len(self._requests)
            total_requests = sum(len(requests) for requests in self._requests.values())

            return {
                "active_clients": active_clients,
                "total_active_requests": total_requests,
                "max_requests_per_window": self.max_requests,
                "window_seconds": self.window_seconds,
            }


class SessionRateLimiter:
    """Specialized rate limiter for session endpoints"""

    def __init__(self):
        # Different limits for different endpoint types
        self.session_info_limiter = RateLimiter(
            max_requests=20, window_seconds=60
        )  # 20 per minute
        self.session_delete_limiter = RateLimiter(
            max_requests=5, window_seconds=60
        )  # 5 per minute
        self.session_create_limiter = RateLimiter(
            max_requests=10, window_seconds=60
        )  # 10 per minute

    def check_session_info_limit(self, client_ip: str) -> bool:
        """Check rate limit for session info requests"""
        return self.session_info_limiter.is_allowed(f"info_{client_ip}")

    def check_session_delete_limit(self, client_ip: str) -> bool:
        """Check rate limit for session delete requests"""
        return self.session_delete_limiter.is_allowed(f"delete_{client_ip}")

    def check_session_create_limit(self, client_ip: str) -> bool:
        """Check rate limit for session create requests"""
        return self.session_create_limiter.is_allowed(f"create_{client_ip}")

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all rate limiters"""
        return {
            "session_info": self.session_info_limiter.get_stats(),
            "session_delete": self.session_delete_limiter.get_stats(),
            "session_create": self.session_create_limiter.get_stats(),
        }


# Global rate limiter instance
_session_rate_limiter: Optional[SessionRateLimiter] = None


import threading

_session_rate_limiter_lock = threading.Lock()


def get_session_rate_limiter() -> SessionRateLimiter:
    """Get the global session rate limiter instance"""
    global _session_rate_limiter
    if _session_rate_limiter is None:
        with _session_rate_limiter_lock:
            if _session_rate_limiter is None:
                _session_rate_limiter = SessionRateLimiter()
    return _session_rate_limiter
