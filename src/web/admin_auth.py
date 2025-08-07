#!/usr/bin/env python3
"""
Minimal Admin Authentication surface to satisfy integration tests.

Features:
- Username/password authentication using ADMIN_USERNAME and
  ADMIN_PASSWORD_HASH via the shared generate_admin_hash.py
  (tests create hashes using this utility).
- In-memory token sessions with expiry.
- Basic IP-based rate limiting with temporary lockout after repeated
  failures.
- Public methods expected by tests:
    * authenticate_admin(username, password, ip) -> Optional[str]
    * validate_admin_session(token, ip) -> bool
    * revoke_admin_session(token, ip) -> bool
    * cleanup_expired_sessions() -> int
    * get_admin_stats() -> dict
    * unlock_ip(ip) -> bool

Security notes:
- This is a test-focused scaffold. Do not use in production without
  strong cryptography, secure token generation, persistence, and
  auditing.
"""

from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

# Reasonable defaults for tests
DEFAULT_SESSION_TIMEOUT_MINUTES = 30
DEFAULT_TOKEN_EXPIRY_HOURS = 8
DEFAULT_RATE_LIMIT_MAX_FAILURES = 5
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60 * 5
DEFAULT_IP_LOCKOUT_SECONDS = 60 * 10


def _now() -> float:
    return time.time()


def _get_env_str(key: str, default: str = "") -> str:
    val = os.getenv(key)
    return val if val is not None else default


def _get_env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass
class AdminAuthenticator:
    secret: Optional[str] = None
    session_timeout_minutes: int = field(
        default_factory=lambda: _get_env_int(
            "ADMIN_SESSION_TIMEOUT_MINUTES", DEFAULT_SESSION_TIMEOUT_MINUTES
        )
    )
    token_expiry_hours: int = field(
        default_factory=lambda: _get_env_int(
            "ADMIN_TOKEN_EXPIRY_HOURS", DEFAULT_TOKEN_EXPIRY_HOURS
        )
    )
    max_failures: int = field(
        default_factory=lambda: _get_env_int(
            "ADMIN_RATE_LIMIT_MAX_FAILURES", DEFAULT_RATE_LIMIT_MAX_FAILURES
        )
    )
    failure_window_seconds: int = field(
        default_factory=lambda: _get_env_int(
            "ADMIN_RATE_LIMIT_WINDOW_SECONDS",
            DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
        )
    )
    ip_lockout_seconds: int = field(
        default_factory=lambda: _get_env_int(
            "ADMIN_IP_LOCKOUT_SECONDS", DEFAULT_IP_LOCKOUT_SECONDS
        )
    )

    # In-memory state
    active_sessions: Dict[str, Dict[str, float | str]] = field(default_factory=dict)
    failed_attempts: Dict[str, list[float]] = field(default_factory=dict)
    locked_ips: Dict[str, float] = field(default_factory=dict)

    def _verify_password(self, username: str, password: str) -> bool:
        """Verify username/password using env and shared hash utility."""
        env_user = _get_env_str("ADMIN_USERNAME")
        env_hash = _get_env_str("ADMIN_PASSWORD_HASH")
        if not env_user or not env_hash:
            return False
        if username != env_user:
            return False

        try:
            # Import the hashing utility exactly like tests do to avoid dep drift
            import importlib.util
            from pathlib import Path

            scripts_path = Path(__file__).resolve().parents[2] / "tests" / "scripts"
            hash_module_path = scripts_path / "generate_admin_hash.py"
            if not hash_module_path.exists():
                return False

            spec = importlib.util.spec_from_file_location(
                "generate_admin_hash", hash_module_path
            )
            if not spec or not spec.loader:
                return False

            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            verify_password = getattr(mod, "verify_password", None)
            if not callable(verify_password):
                return False
            return bool(verify_password(password, env_hash))
        except Exception:
            # Log the exception in production scenarios
            return False

    def _is_ip_locked(self, ip: str, now: Optional[float] = None) -> bool:
        if not ip:
            return False
        now = now or _now()
        until = self.locked_ips.get(ip)
        if until and until > now:
            return True
        if until and until <= now:
            # Lock expired
            self.locked_ips.pop(ip, None)
        return False

    def _record_failure(self, ip: str, now: Optional[float] = None) -> None:
        if not ip:
            return
        now = now or _now()
        window_start = now - self.failure_window_seconds
        attempts = [t for t in self.failed_attempts.get(ip, []) if t >= window_start]
        attempts.append(now)
        self.failed_attempts[ip] = attempts
        if len(attempts) >= self.max_failures:
            self.locked_ips[ip] = now + self.ip_lockout_seconds

    # Public API expected by tests

    def authenticate_admin(
        self, username: str, password: str, ip: str
    ) -> Optional[str]:
        """Return access token on success; None on failure or lockout."""
        if self._is_ip_locked(ip):
            return None

        if not self._verify_password(username, password):
            self._record_failure(ip)
            return None

        # Success: clear recent failures for the IP
        if ip in self.failed_attempts:
            del self.failed_attempts[ip]

        token = secrets.token_urlsafe(32)
        now = _now()
        self.active_sessions[token] = {
            "created_at": now,
            "expires_at": now + (self.token_expiry_hours * 3600),
            "ip": ip,
            "username": username,
        }
        return token

    def validate_admin_session(self, token: str, ip: str) -> bool:
        """Validate token, refresh last access, and enforce expiry."""
        if not token:
            return False
        sess = self.active_sessions.get(token)
        if not sess:
            return False
        now = _now()
        if now >= float(sess["expires_at"]):
            # Expired: remove
            self.active_sessions.pop(token, None)
            return False
        # Optionally enforce simple IP binding
        if ip and sess.get("ip") and sess["ip"] != ip:
            return False
        # Refresh expiry on activity within session timeout window
        sess["last_access"] = now
        return True

    def revoke_admin_session(self, token: str, ip: str) -> bool:
        """
        Revoke an active session.

        Security note:
        - We accept `ip` for API consistency with other methods.
        - If you want stricter binding, enable IP verification below.
        """
        sess = self.active_sessions.get(token)
        if not sess:
            return False

        # Optional IP verification: uncomment to require same-IP revocation
        # If enabled, only the IP that created the session can revoke it.
        # if ip and sess.get("ip") and sess["ip"] != ip:
        #     return False

        self.active_sessions.pop(token, None)
        return True

    def cleanup_expired_sessions(self) -> int:
        """Remove expired tokens; return count removed."""
        now = _now()
        to_delete = [
            t for t, s in self.active_sessions.items() if now >= float(s["expires_at"])
        ]
        for t in to_delete:
            self.active_sessions.pop(t, None)
        return len(to_delete)

    def get_admin_stats(self) -> Dict[str, Any]:
        """Return a stats snapshot used by tests."""
        return {
            "active_admin_sessions": len(self.active_sessions),
            "session_timeout_minutes": self.session_timeout_minutes,
            "token_expiry_hours": self.token_expiry_hours,
            "sessions": list(self.active_sessions.keys()),
            "rate_limiting": {
                "failed_attempts": {k: len(v) for k, v in self.failed_attempts.items()},
                "locked_ips": list(self.locked_ips.keys()),
                "max_failures": self.max_failures,
                "window_seconds": self.failure_window_seconds,
                "lockout_seconds": self.ip_lockout_seconds,
            },
        }

    def unlock_ip(self, ip: str) -> bool:
        """Manually unlock an IP address."""
        if ip in self.locked_ips:
            self.locked_ips.pop(ip, None)
            # Optionally clear failures too
            self.failed_attempts.pop(ip, None)
            return True
        return False


def get_admin_authenticator(
    secret: Optional[str] = None,
) -> AdminAuthenticator:
    # Secret is unused in tests but kept for backwards compatibility.
    return AdminAuthenticator(secret=secret)


def verify_admin_access(token: str, secret: Optional[str] = None) -> bool:
    # Backwards compatible helper calling validate_admin_session without
    # IP binding.
    return get_admin_authenticator(secret).validate_admin_session(
        token,
        ip="",
    )
