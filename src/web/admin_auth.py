#!/usr/bin/env python3
"""
Admin Authentication and Authorization
Provides secure access control for administrative endpoints
"""

import os
import secrets
import hashlib
import hmac
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# Security configuration
ADMIN_TOKEN_EXPIRY_HOURS = 24
ADMIN_SESSION_TIMEOUT_MINUTES = 30


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
            logger.warning("Admin secret key not configured, using generated key (development only)")
        
        # Generate default password hash if not provided (for development)
        if not self.admin_password_hash:
            default_password = "admin123"  # Change this in production!
            self.admin_password_hash = self._hash_password(default_password)
            logger.warning(f"Admin password not configured, using default password '{default_password}' (CHANGE IN PRODUCTION!)")
        
        # Active admin sessions (in-memory for simplicity)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        logger.info("AdminAuthenticator initialized")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using PBKDF2 with salt"""
        salt = secrets.token_bytes(32)
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return salt.hex() + ':' + pwdhash.hex()
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            salt_hex, pwdhash_hex = password_hash.split(':')
            salt = bytes.fromhex(salt_hex)
            pwdhash = bytes.fromhex(pwdhash_hex)
            
            # Hash the provided password with the same salt
            test_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            
            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(pwdhash, test_hash)
        except (ValueError, TypeError):
            return False
    
    def authenticate_admin(self, username: str, password: str, client_ip: str) -> Optional[str]:
        """
        Authenticate admin user and return session token
        
        Args:
            username: Admin username
            password: Admin password
            client_ip: Client IP address for logging
            
        Returns:
            Session token if authentication successful, None otherwise
        """
        # Verify credentials
        if username != self.admin_username or not self._verify_password(password, self.admin_password_hash):
            logger.warning(f"Failed admin login attempt from IP {client_ip} with username '{username}'")
            return None
        
        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        
        # Store session info
        self.active_sessions[session_token] = {
            "username": username,
            "client_ip": client_ip,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=ADMIN_TOKEN_EXPIRY_HOURS)
        }
        
        logger.info(f"Admin user '{username}' authenticated successfully from IP {client_ip}")
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
            logger.info(f"Admin session expired for user '{session['username']}' from IP {client_ip}")
            del self.active_sessions[token]
            return False
        
        # Check session timeout (inactivity)
        if now > session["last_activity"] + timedelta(minutes=ADMIN_SESSION_TIMEOUT_MINUTES):
            logger.info(f"Admin session timed out for user '{session['username']}' from IP {client_ip}")
            del self.active_sessions[token]
            return False
        
        # Check IP consistency (optional security measure)
        if session["client_ip"] != client_ip:
            logger.warning(f"Admin session IP mismatch: expected {session['client_ip']}, got {client_ip}")
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
            logger.info(f"Admin session revoked for user '{session['username']}' from IP {client_ip}")
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
        """Clean up expired admin sessions"""
        now = datetime.now()
        expired_tokens = []
        
        for token, session in self.active_sessions.items():
            if (now > session["expires_at"] or 
                now > session["last_activity"] + timedelta(minutes=ADMIN_SESSION_TIMEOUT_MINUTES)):
                expired_tokens.append(token)
        
        for token in expired_tokens:
            session = self.active_sessions[token]
            logger.info(f"Cleaning up expired admin session for user '{session['username']}'")
            del self.active_sessions[token]
        
        return len(expired_tokens)
    
    def get_admin_stats(self) -> Dict[str, Any]:
        """Get admin authentication statistics"""
        active_sessions = len(self.active_sessions)
        
        # Get session details
        sessions_info = []
        for token, session in self.active_sessions.items():
            sessions_info.append({
                "username": session["username"],
                "client_ip": session["client_ip"],
                "created_at": session["created_at"].isoformat(),
                "last_activity": session["last_activity"].isoformat(),
                "expires_at": session["expires_at"].isoformat()
            })
        
        return {
            "active_admin_sessions": active_sessions,
            "session_timeout_minutes": ADMIN_SESSION_TIMEOUT_MINUTES,
            "token_expiry_hours": ADMIN_TOKEN_EXPIRY_HOURS,
            "sessions": sessions_info
        }


# Global admin authenticator instance
_admin_authenticator: Optional[AdminAuthenticator] = None


def get_admin_authenticator() -> AdminAuthenticator:
    """Get the global admin authenticator instance"""
    global _admin_authenticator
    if _admin_authenticator is None:
        _admin_authenticator = AdminAuthenticator()
    return _admin_authenticator


async def verify_admin_access(
    request: Request,
    authorization: Optional[str] = Header(None)
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
        logger.warning(f"Admin access attempt without authorization header from IP {client_ip}")
        raise HTTPException(
            status_code=401,
            detail="Admin access requires authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract bearer token
    if not authorization.startswith("Bearer "):
        logger.warning(f"Admin access attempt with invalid authorization format from IP {client_ip}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    
    # Validate admin session
    authenticator = get_admin_authenticator()
    if not authenticator.validate_admin_session(token, client_ip):
        raise HTTPException(
            status_code=403,
            detail="Invalid or expired admin session"
        )
    
    return True