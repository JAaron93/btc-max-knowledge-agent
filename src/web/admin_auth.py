#!/usr/bin/env python3
"""
Admin Authentication and Authorization
Provides secure access control for administrative endpoints
"""

import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

# Security configuration
ADMIN_TOKEN_EXPIRY_HOURS = 24
ADMIN_SESSION_TIMEOUT_MINUTES = 30

# Rate limiting configuration
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AdminAuthenticator:
    """Handles admin authentication and authorization"""

    def __init__(self):
        # Load admin credentials from environment
        self.admin_username = os.getenv("ADMIN_USERNAME", "admin")
        self.admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH")
        self.admin_secret_key = os.getenv("ADMIN_SECRET_KEY")

        # Generate secret key if not provided (for development)
        if not self.admin_secret_key:
            self.admin_secret_key = secrets.token_hex(32)
            logger.warning(
                "Admin secret key not configured, using generated key (development only)"
            )

        # Validate admin password hash is configured
        if not self.admin_password_hash:
            error_msg = (
                "Admin password hash not configured. "
                "Set ADMIN_PASSWORD_HASH environment variable or run: "
                "python3 scripts/generate_admin_hash.py"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Active admin sessions (in-memory for simplicity)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

        # Rate limiting tracking
        self.failed_attempts: Dict[str, Dict[str, Any]] = {}

        # Argon2id password hasher (OWASP recommended)
        self.password_hasher = PasswordHasher()

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval_minutes = 5  # Run cleanup every 5 minutes

        # Monitoring state attributes that survive event-loop restarts
        self._cleanup_restart_attempts: int = 0
        self._cleanup_last_start: Optional[datetime] = None
        self._cleanup_backoff: float = (
            1.0  # Exponential backoff multiplier for restart delays
        )
        self._cleanup_max_backoff: float = (
            300.0  # Maximum backoff delay in seconds (5 minutes)
        )
        self._cleanup_restart_window: timedelta = timedelta(
            hours=1
        )  # Reset counter after this window
        self._cleanup_max_restarts_per_window: int = (
            10  # Max restarts allowed per window
        )

        logger.info("AdminAuthenticator initialized")

    def _hash_password(self, password: str) -> str:
        """Hash password using Argon2id (OWASP recommended)"""
        return self.password_hasher.hash(password)

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against Argon2id hash"""
        try:
            self.password_hasher.verify(password_hash, password)
            return True
        except VerifyMismatchError:
            return False

    def _is_ip_locked_out(self, client_ip: str) -> bool:
        """Check if an IP address is currently locked out"""
        if client_ip not in self.failed_attempts:
            return False

        attempt_data = self.failed_attempts[client_ip]

        # Check if lockout has expired
        if "locked_until" in attempt_data:
            if datetime.now() > attempt_data["locked_until"]:
                # Lockout expired, clear the record
                del self.failed_attempts[client_ip]
                return False
            return True

        return False

    def _record_failed_attempt(self, client_ip: str):
        """Record a failed login attempt for an IP address"""
        now = datetime.now()

        if client_ip not in self.failed_attempts:
            self.failed_attempts[client_ip] = {
                "count": 1,
                "first_attempt": now,
                "last_attempt": now,
            }
        else:
            self.failed_attempts[client_ip]["count"] += 1
            self.failed_attempts[client_ip]["last_attempt"] = now

        attempt_data = self.failed_attempts[client_ip]

        # Check if we should lock out this IP
        if attempt_data["count"] >= MAX_LOGIN_ATTEMPTS:
            lockout_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            attempt_data["locked_until"] = lockout_until
            logger.warning(
                f"IP {client_ip} locked out after {attempt_data['count']} "
                f"failed attempts. Lockout until: {lockout_until}"
            )
        else:
            logger.warning(
                f"Failed login attempt {attempt_data['count']}/{MAX_LOGIN_ATTEMPTS} "
                f"from IP {client_ip}"
            )

    def _clear_failed_attempts(self, client_ip: str):
        """Clear failed login attempts for an IP address after successful login"""
        if client_ip in self.failed_attempts:
            del self.failed_attempts[client_ip]
            logger.debug(f"Cleared failed login attempts for IP {client_ip}")

    def authenticate_admin(
        self, username: str, password: str, client_ip: str
    ) -> Optional[str]:
        """
        Authenticate admin user and return session token

        Args:
            username: Admin username
            password: Admin password
            client_ip: Client IP address for logging

        Returns:
            Session token if authentication successful, None otherwise
        """
        # Check if IP is locked out due to too many failed attempts
        if self._is_ip_locked_out(client_ip):
            logger.warning(f"Login attempt from locked out IP {client_ip}")
            return None

        # Verify credentials
        if username != self.admin_username or not self._verify_password(
            password, self.admin_password_hash
        ):
            self._record_failed_attempt(client_ip)
            logger.warning(
                f"Failed admin login attempt from IP {client_ip} with username '{username}'"
            )
            return None

        # Clear any previous failed attempts on successful login
        self._clear_failed_attempts(client_ip)

        # Generate secure session token
        session_token = secrets.token_urlsafe(32)

        # Store session info
        self.active_sessions[session_token] = {
            "username": username,
            "client_ip": client_ip,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=ADMIN_TOKEN_EXPIRY_HOURS),
        }

        logger.info(
            f"Admin user '{username}' authenticated successfully from IP {client_ip}"
        )
        return session_token

    def validate_admin_session(self, token: str, client_ip: str) -> bool:
        """
        Validate admin session token

        Args:
            token: Session token
            client_ip: Client IP address

        Returns:
            True if session is valid, False otherwise
        """

        if not token or token not in self.active_sessions:
            logger.warning(f"Invalid admin session token from IP {client_ip}")
            return False

        session = self.active_sessions[token]
        now = datetime.now()

        # Check if session has expired
        if now > session["expires_at"]:
            logger.info(
                f"Admin session expired for user '{session['username']}' from IP {client_ip}"
            )
            del self.active_sessions[token]
            return False

        # Check session timeout (inactivity)
        if now > session["last_activity"] + timedelta(
            minutes=ADMIN_SESSION_TIMEOUT_MINUTES
        ):
            logger.info(
                f"Admin session timed out for user '{session['username']}' from IP {client_ip}"
            )
            del self.active_sessions[token]
            return False

        # Check IP consistency (optional security measure)
        if session["client_ip"] != client_ip:
            logger.warning(
                f"Admin session IP mismatch: expected {session['client_ip']}, got {client_ip}"
            )
            # Don't fail here as IPs can change legitimately, but log for monitoring

        # Update last activity
        session["last_activity"] = now

        return True

    def revoke_admin_session(self, token: str, client_ip: str) -> bool:
        """
        Revoke admin session

        Args:
            token: Session token to revoke
            client_ip: Client IP address

        Returns:
            True if session was revoked, False if not found
        """
        if token in self.active_sessions:
            session = self.active_sessions[token]
            logger.info(
                f"Admin session revoked for user '{session['username']}' from IP {client_ip}"
            )
            del self.active_sessions[token]
            return True
        return False

    def get_admin_session_info(self, token: str) -> Optional[Dict[str, Any]]:
        """Get admin session information"""
        if token in self.active_sessions:
            session = self.active_sessions[token].copy()
            # Convert datetime objects to strings for JSON serialization
            session["created_at"] = session["created_at"].isoformat()
            session["last_activity"] = session["last_activity"].isoformat()
            session["expires_at"] = session["expires_at"].isoformat()
            return session
        return None

    def cleanup_expired_sessions(self):
        """Clean up expired admin sessions and lockouts"""
        now = datetime.now()
        expired_tokens = []

        # Clean up expired sessions
        for token, session in self.active_sessions.items():
            if now > session["expires_at"] or now > session[
                "last_activity"
            ] + timedelta(minutes=ADMIN_SESSION_TIMEOUT_MINUTES):
                expired_tokens.append(token)

        for token in expired_tokens:
            session = self.active_sessions[token]
            logger.info(
                f"Cleaning up expired admin session for user '{session['username']}'"
            )
            del self.active_sessions[token]

        # Clean up expired lockouts
        expired_ips = []
        for ip, attempt_data in self.failed_attempts.items():
            if "locked_until" in attempt_data and now > attempt_data["locked_until"]:
                expired_ips.append(ip)

        for ip in expired_ips:
            logger.info(f"Cleaning up expired lockout for IP {ip}")
            del self.failed_attempts[ip]

        return len(expired_tokens)

    def get_admin_stats(self) -> Dict[str, Any]:
        """Get admin authentication statistics"""
        active_sessions = len(self.active_sessions)

        # Get session details
        sessions_info = []
        for token, session in self.active_sessions.items():
            sessions_info.append(
                {
                    "username": session["username"],
                    "client_ip": session["client_ip"],
                    "created_at": session["created_at"].isoformat(),
                    "last_activity": session["last_activity"].isoformat(),
                    "expires_at": session["expires_at"].isoformat(),
                }
            )

        # Get rate limiting info
        locked_ips = []
        failed_attempts_info = []
        now = datetime.now()

        for ip, attempt_data in self.failed_attempts.items():
            if "locked_until" in attempt_data:
                if now < attempt_data["locked_until"]:
                    locked_ips.append(
                        {
                            "ip": ip,
                            "locked_until": attempt_data["locked_until"].isoformat(),
                            "failed_attempts": attempt_data["count"],
                        }
                    )
            else:
                failed_attempts_info.append(
                    {
                        "ip": ip,
                        "failed_attempts": attempt_data["count"],
                        "first_attempt": attempt_data["first_attempt"].isoformat(),
                        "last_attempt": attempt_data["last_attempt"].isoformat(),
                    }
                )

        # Include cleanup monitoring stats
        cleanup_stats = {
            "cleanup_task_running": self._cleanup_task is not None
            and not self._cleanup_task.done(),
            "cleanup_restart_attempts": self._cleanup_restart_attempts,
            "cleanup_last_start": (
                self._cleanup_last_start.isoformat()
                if self._cleanup_last_start
                else None
            ),
            "cleanup_backoff_seconds": self._cleanup_backoff,
            "cleanup_max_backoff_seconds": self._cleanup_max_backoff,
            "cleanup_max_restarts_per_window": self._cleanup_max_restarts_per_window,
            "cleanup_restart_window_hours": self._cleanup_restart_window.total_seconds()
            / 3600,
        }

        return {
            "active_admin_sessions": active_sessions,
            "session_timeout_minutes": ADMIN_SESSION_TIMEOUT_MINUTES,
            "token_expiry_hours": ADMIN_TOKEN_EXPIRY_HOURS,
            "sessions": sessions_info,
            "rate_limiting": {
                "max_login_attempts": MAX_LOGIN_ATTEMPTS,
                "lockout_duration_minutes": LOCKOUT_DURATION_MINUTES,
                "locked_ips": locked_ips,
                "failed_attempts": failed_attempts_info,
            },
            "cleanup_monitoring": cleanup_stats,
        }

    def unlock_ip(self, client_ip: str) -> bool:
        """
        Manually unlock an IP address (admin function)

        Args:
            client_ip: IP address to unlock

        Returns:
            True if IP was unlocked, False if not found or not locked
        """
        if client_ip in self.failed_attempts:
            del self.failed_attempts[client_ip]
            logger.info(f"Manually unlocked IP address: {client_ip}")
            return True
        return False

    def _should_allow_cleanup_restart(self) -> bool:
        """Check if cleanup task restart should be allowed based on monitoring state"""
        now = datetime.now()

        # Reset restart count if outside the restart window
        if (
            self._cleanup_last_start
            and now - self._cleanup_last_start > self._cleanup_restart_window
        ):
            self._cleanup_restart_attempts = 0
            self._cleanup_backoff = 1.0
            logger.debug("Reset cleanup restart attempts counter after window expiry")

        # Check if we've exceeded max restarts for this window
        if self._cleanup_restart_attempts >= self._cleanup_max_restarts_per_window:
            logger.warning(
                f"Cleanup task restart limit reached ({self._cleanup_restart_attempts}/ "
                f"{self._cleanup_max_restarts_per_window} in {self._cleanup_restart_window}). "
                "Blocking further restarts."
            )
            return False

        return True

# At the top of src/web/admin_auth.py, alongside the other imports:
import asyncio
import logging
import os
import random
import secrets

# …

    def _record_cleanup_restart(self) -> None:
        """Record a cleanup task restart and update monitoring state"""
        now = datetime.now()
        self._cleanup_restart_attempts += 1
        self._cleanup_last_start = now

        # Apply exponential backoff with jitter
        jitter = random.uniform(0.8, 1.2)  # Add 20% jitter
        self._cleanup_backoff = min(
            self._cleanup_backoff * 2 * jitter, self._cleanup_max_backoff
        )

        logger.info(
            f"Cleanup task restart #{self._cleanup_restart_attempts} recorded. "
            f"Next backoff: {self._cleanup_backoff:.1f}s"
        )

    def _reset_cleanup_monitoring_state(self) -> None:
        """Reset cleanup monitoring state (useful for manual intervention)"""
        self._cleanup_restart_attempts = 0
        self._cleanup_last_start = None
        self._cleanup_backoff = 1.0
        logger.info("Cleanup monitoring state reset")

    def get_cleanup_monitoring_state(self) -> Dict[str, Any]:
        """Get current cleanup monitoring state for debugging/admin purposes"""
        return {
            "restart_attempts": self._cleanup_restart_attempts,
            "last_start": (
                self._cleanup_last_start.isoformat()
                if self._cleanup_last_start
                else None
            ),
            "current_backoff_seconds": self._cleanup_backoff,
            "max_backoff_seconds": self._cleanup_max_backoff,
            "restart_window_hours": self._cleanup_restart_window.total_seconds() / 3600,
            "max_restarts_per_window": self._cleanup_max_restarts_per_window,
            "task_running": self._cleanup_task is not None
            and not self._cleanup_task.done(),
            "can_restart": self._should_allow_cleanup_restart(),
        }

    async def _background_cleanup_task(self):
        """Background task to periodically clean up expired sessions"""
        while True:
            try:
                await asyncio.sleep(
                    self._cleanup_interval_minutes * 60
                )  # Convert to seconds
                expired_count = self.cleanup_expired_sessions()
                if expired_count > 0:
                    logger.info(
                        f"Background cleanup removed {expired_count} expired admin sessions"
                    )
                else:
                    logger.debug("Background cleanup found no expired admin sessions")
            except asyncio.CancelledError:
                logger.info("Admin session background cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in admin session background cleanup: {e}")
                # Continue running despite errors

    def _on_cleanup_done(self, task: asyncio.Task) -> None:
        """Callback invoked when cleanup task completes"""
        try:
            # Inspect task result/exception
            if task.cancelled():
                logger.info("Cleanup task was cancelled")
            elif task.exception():
                exc = task.exception()
                logger.error(f"Cleanup task finished with exception: {exc}")
                # Schedule restart if it finished unexpectedly (due to exception)
                if self._should_allow_cleanup_restart():
                    logger.info(
                        "Scheduling cleanup task restart due to unexpected completion"
                    )
                    asyncio.create_task(self._restart_cleanup())
                else:
                    logger.warning(
                        "Cleanup task restart blocked due to monitoring limits"
                    )
            else:
                # Task completed normally (should not happen for infinite loop)
                result = task.result()
                logger.warning(
                    f"Cleanup task completed unexpectedly with result: {result}"
                )
                # Schedule restart if it finished unexpectedly
                if self._should_allow_cleanup_restart():
                    logger.info(
                        "Scheduling cleanup task restart due to unexpected completion"
                    )
                    asyncio.create_task(self._restart_cleanup())
                else:
                    logger.warning(
                        "Cleanup task restart blocked due to monitoring limits"
                    )
        except Exception as e:
            logger.error(f"Error in cleanup task completion callback: {e}")

    async def _restart_cleanup(self) -> None:
        """Restart the cleanup task with backoff delay"""
        try:
            # Apply backoff delay before restarting
            logger.info(
                f"Waiting {self._cleanup_backoff:.1f}s before restarting cleanup task"
            )
            await asyncio.sleep(self._cleanup_backoff)

            # Start background cleanup again
            self.start_background_cleanup()
        except Exception as e:
            logger.error(f"Error restarting cleanup task: {e}")

    def start_background_cleanup(self):
        """Start the background cleanup task"""
        if (
            self._cleanup_task is None or self._cleanup_task.done()
        ) and self._should_allow_cleanup_restart():
            try:
                loop = asyncio.get_event_loop()
                self._cleanup_task = loop.create_task(self._background_cleanup_task())
                # Add task completion callback
                self._cleanup_task.add_done_callback(self._on_cleanup_done)
                self._record_cleanup_restart()
                logger.info(
                    f"Started admin session background cleanup task with completion callback (interval: {self._cleanup_interval_minutes} minutes)"
                )
            except RuntimeError:
                # No event loop running, this is expected in some contexts
                logger.warning(
                    "Cannot start background cleanup task: no event loop running"
                )

    def stop_background_cleanup(self):
        """Stop the background cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Stopped admin session background cleanup task")


# Global admin authenticator instance
_admin_authenticator: Optional[AdminAuthenticator] = None


def get_admin_authenticator() -> AdminAuthenticator:
    """Get the global admin authenticator instance"""
    global _admin_authenticator
    if _admin_authenticator is None:
        _admin_authenticator = AdminAuthenticator()
    return _admin_authenticator


async def verify_admin_access(
    request: Request, authorization: Optional[str] = Header(None)
) -> bool:
    """
    Dependency to verify admin access

    Args:
        request: FastAPI request object
        authorization: Authorization header

    Returns:
        True if admin access is valid

    Raises:
        HTTPException: If access is denied
    """
    client_ip = request.client.host if request.client else "unknown"

    # Check for authorization header
    if not authorization:
        logger.warning(
            f"Admin access attempt without authorization header from IP {client_ip}"
        )
        raise HTTPException(
            status_code=401,
            detail="Admin access requires authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract bearer token
    if not authorization.startswith("Bearer "):
        logger.warning(
            f"Admin access attempt with invalid authorization format from IP {client_ip}"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    # Validate admin session
    authenticator = get_admin_authenticator()
    if not authenticator.validate_admin_session(token, client_ip):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired admin session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
