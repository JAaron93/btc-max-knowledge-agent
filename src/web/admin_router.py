#!/usr/bin/env python3
"""
Admin Router with Protected Endpoints
Provides secure administrative functionality
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from .admin_auth import get_admin_authenticator, verify_admin_access
from .rate_limiter import get_session_rate_limiter

logger = logging.getLogger(__name__)

# Create admin router
admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_access)],  # All endpoints require admin access
    responses={
        401: {"description": "Unauthorized - Missing or invalid authorization"},
        403: {"description": "Forbidden - Invalid or expired admin session"},
        500: {"description": "Internal server error"},
    },
)


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = 24
    message: str


@admin_router.post("/login", dependencies=[], response_model=AdminLoginResponse)
async def admin_login(request: Request, login_data: AdminLoginRequest):
    """
    Admin login endpoint (not protected by admin auth dependency)

    Returns admin access token for subsequent requests
    """
    client_ip = request.client.host if request.client else "unknown"

    authenticator = get_admin_authenticator()

    # Authenticate admin
    session_token = authenticator.authenticate_admin(
        login_data.username, login_data.password, client_ip
    )

    if not session_token:
        # Add delay to prevent brute force attacks

        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    return AdminLoginResponse(
        access_token=session_token, message="Admin authentication successful"
    )


@admin_router.post("/logout")
async def admin_logout(request: Request, authorization: Optional[str] = Header(None)):
    """Admin logout endpoint"""
    client_ip = request.client.host if request.client else "unknown"

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        authenticator = get_admin_authenticator()
        revoked = authenticator.revoke_admin_session(token, client_ip)

        if revoked:
            return {"message": "Admin session revoked successfully"}

    return {"message": "No active session to revoke"}


@admin_router.get("/session/info")
async def get_admin_session_info(request: Request, authorization: Optional[str] = None):
    """Get current admin session information"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        authenticator = get_admin_authenticator()
        session_info = authenticator.get_admin_session_info(token)

        if session_info:
            return {"session_info": session_info, "timestamp": time.time()}

    raise HTTPException(status_code=404, detail="Session information not found")


@admin_router.get("/sessions/stats")
async def get_session_stats():
    """Get session statistics (admin only)"""
    try:
        # Import here to avoid circular imports
        from .bitcoin_assistant_api import bitcoin_service

        if not bitcoin_service:
            raise HTTPException(status_code=503, detail="Service not initialized")

        stats = bitcoin_service.session_manager.get_session_stats()

        logger.info("Admin accessed session statistics")

        return {
            "session_statistics": stats,
            "timestamp": time.time(),
            "admin_access": True,
        }
    except Exception as e:
        logger.error(f"Failed to get session stats for admin: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get session stats: {str(e)}"
        )


@admin_router.post("/sessions/cleanup")
async def cleanup_expired_sessions():
    """Force cleanup of expired sessions (admin only)"""
    try:
        # Import here to avoid circular imports
        from .bitcoin_assistant_api import bitcoin_service

        if not bitcoin_service:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Cleanup user sessions
        bitcoin_service.session_manager.cleanup_expired_sessions()
        stats = bitcoin_service.session_manager.get_session_stats()

        # Also cleanup admin sessions
        authenticator = get_admin_authenticator()
        expired_admin_sessions = authenticator.cleanup_expired_sessions()

        logger.info("Admin triggered session cleanup")

        return {
            "message": "Expired sessions cleaned up",
            "user_session_stats": stats,
            "expired_admin_sessions": expired_admin_sessions,
            "timestamp": time.time(),
            "admin_access": True,
        }
    except Exception as e:
        logger.error(f"Failed to cleanup sessions for admin: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cleanup sessions: {str(e)}"
        )


@admin_router.get("/sessions/rate-limits")
async def get_rate_limit_stats():
    """Get rate limiter statistics for monitoring (admin only)"""
    try:
        rate_limiter = get_session_rate_limiter()
        stats = rate_limiter.get_all_stats()

        logger.info("Admin accessed rate limit statistics")

        actual_limits = rate_limiter.get_configured_limits()
        return {
            "rate_limit_stats": stats,
            "timestamp": time.time(),
            "limits": actual_limits,
            "admin_access": True,
        }
    except Exception as e:
        logger.error(f"Failed to get rate limit stats for admin: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get rate limit stats: {str(e)}"
        )


@admin_router.get("/sessions/list")
async def list_all_sessions(skip: int = 0, limit: int = 100):
    if limit > 1000:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 1000")
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip cannot be negative")

    """List all active sessions (admin only)"""
    try:
        # Import here to avoid circular imports
        from .bitcoin_assistant_api import bitcoin_service

        if not bitcoin_service:
            raise HTTPException(status_code=503, detail="Service not initialized")

        sessions = bitcoin_service.session_manager.list_sessions(skip=skip, limit=limit)

        logger.info(f"Admin accessed session list ({len(sessions)} sessions)")

        return {
            "sessions": sessions,
            "displayed_sessions": len(sessions),
            "skip": skip,
            "limit": limit,
            "timestamp": time.time(),
            "admin_access": True,
        }
    except Exception as e:
        logger.error(f"Failed to list sessions for admin: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list sessions: {str(e)}"
        )


@admin_router.delete("/sessions/{session_id}")
async def force_delete_session(session_id: str):
    """Force delete any session (admin only)"""
    try:
        # Import here to avoid circular imports
        from .bitcoin_assistant_api import bitcoin_service

        if not bitcoin_service:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Admin can delete any session without ownership validation
        removed = bitcoin_service.session_manager.remove_session(session_id)

        if removed:
            logger.warning(f"Admin force-deleted session: {session_id[:8]}...")
            return {
                "message": "Session force-deleted successfully",
                "session_id": session_id,
                "deleted_at": time.time(),
                "admin_access": True,
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to force delete session {session_id[:8]}... for admin: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete session: {str(e)}"
        )


@admin_router.get("/auth/stats")
async def get_admin_auth_stats():
    """Get admin authentication statistics"""
    try:
        authenticator = get_admin_authenticator()
        stats = authenticator.get_admin_stats()

        logger.info("Admin accessed authentication statistics")

        return {"admin_auth_stats": stats, "timestamp": time.time()}
    except Exception as e:
        logger.error(f"Failed to get admin auth stats: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get admin auth stats: {str(e)}"
        )


@admin_router.get("/health")
async def admin_health_check():
    """Admin health check endpoint"""
    try:
        # Import here to avoid circular imports
        from .bitcoin_assistant_api import bitcoin_service

        # Check service status
        service_status = "initialized" if bitcoin_service else "not_initialized"

        # Check admin auth status
        authenticator = get_admin_authenticator()
        admin_stats = authenticator.get_admin_stats()

        # Check rate limiter status
        rate_limiter = get_session_rate_limiter()
        rate_stats = rate_limiter.get_all_stats()

        return {
            "status": "healthy",
            "service_status": service_status,
            "admin_sessions": admin_stats["active_admin_sessions"],
            "rate_limiter_clients": sum(
                stat["active_clients"] for stat in rate_stats.values()
            ),
            "timestamp": time.time(),
            "admin_access": True,
        }
    except Exception as e:
        logger.error(f"Admin health check failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Admin health check failed: {str(e)}"
        )
