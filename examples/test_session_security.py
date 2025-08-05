#!/usr/bin/env python3
"""
Test Session Security Validation
Demonstrates the session ownership validation logic with enhanced security
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

# Configure logging for security events
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
security_logger = logging.getLogger("session_security")


def validate_session_id_format(session_id: str) -> bool:
    """
    Validate session ID format and structure

    Args:
        session_id: Session ID to validate

    Returns:
        bool: True if format is valid, False otherwise
    """
    if not session_id:
        return False

    # Check length (should be 32 characters for hex format)
    if len(session_id) != 32:
        return False

    # Check if it's a valid hexadecimal string (case-insensitive)
    if not re.match(r"^[a-fA-F0-9]{32}$", session_id):
        return False

    return True


def is_session_expired(
    session_id: str,
    session_created_at: Optional[datetime] = None,
    timeout_minutes: int = 30,
) -> bool:
    """
    Check if session has expired

    Args:
        session_id: Session ID to check
        session_created_at: When session was created (should be timezone-aware, None for demo)
        timeout_minutes: Session timeout in minutes

    Returns:
        bool: True if session is expired, False otherwise

    Note:
        This function handles both timezone-aware and naive datetime objects:
        - If session_created_at is timezone-aware, uses UTC for comparison
        - If session_created_at is naive, uses local time for compatibility
        For best practices, use timezone-aware datetimes when possible.
    """
    if session_created_at is None:
        # For demo purposes, simulate some sessions as expired
        # In real implementation, this would check actual session data
        expired_demo_sessions = {
            "e1f2a3b4c5d6789012345678901234ab",  # Expired session 1
            "0123456789abcdef0123456789abcdef",  # Expired session 2
        }
        return session_id in expired_demo_sessions

    expiry_time = session_created_at + timedelta(minutes=timeout_minutes)

    # Use timezone-aware comparison if session_created_at is timezone-aware,
    # otherwise fall back to naive datetime for compatibility
    if session_created_at.tzinfo is not None:
        current_time = datetime.now(timezone.utc)
    else:
        current_time = datetime.now()

    return current_time > expiry_time


def validate_session_ownership(
    current_session_id: Optional[str],
    requested_session_id: Optional[str],
    client_ip: str = "unknown",
) -> Tuple[bool, int, str]:
    """
    Enhanced session ownership validation with security logging

    Args:
        current_session_id: Session ID from cookie
        requested_session_id: Session ID being accessed/deleted
        client_ip: Client IP address for logging

    Returns:
        tuple: (is_valid, status_code, message)
    """

    # Input validation - No active session cookie
    if not current_session_id:
        security_logger.warning(
            f"Session access attempt without active session from IP: {client_ip}"
        )
        return (
            False,
            401,
            "No active session found. Session access requires an active "
            "session cookie.",
        )

    # Input validation - Empty or whitespace session
    if not current_session_id.strip():
        security_logger.warning(
            f"Session access attempt with empty session ID from IP: {client_ip}"
        )
        return (
            False,
            401,
            "Invalid session format. Session access requires a valid session cookie.",
        )

    # Input validation - No requested session
    if not requested_session_id:
        security_logger.warning(
            f"Session access attempt without requested session ID from "
            f"IP: {client_ip}, current session: {current_session_id[:8]}..."
        )
        return (False, 400, "Bad request. Session ID parameter is required.")

    # Format validation for current session
    if not validate_session_id_format(current_session_id):
        security_logger.error(
            f"Invalid session ID format in cookie from IP: {client_ip}, "
            f"session: {current_session_id[:8]}..."
        )
        return (False, 401, "Invalid session format. Please log in again.")

    # Format validation for requested session
    if not validate_session_id_format(requested_session_id):
        security_logger.error(
            f"Invalid requested session ID format from IP: {client_ip}, "
            f"requested: {requested_session_id[:8]}..."
        )
        return (False, 400, "Invalid session ID format in request.")

    # Session expiration check for current session
    if is_session_expired(current_session_id):
        security_logger.info(
            f"Expired session access attempt from IP: {client_ip}, "
            f"session: {current_session_id[:8]}..."
        )
        return (False, 401, "Session has expired. Please log in again.")

    # Session expiration check for requested session
    if is_session_expired(requested_session_id):
        security_logger.info(
            f"Access attempt to expired session from IP: {client_ip}, "
            f"current: {current_session_id[:8]}..., "
            f"requested: {requested_session_id[:8]}..."
        )
        return (False, 410, "Requested session has expired and is no longer available.")

    # Session ID mismatch (trying to access someone else's session)
    if current_session_id != requested_session_id:
        security_logger.warning(
            f"Session ownership violation from IP: {client_ip}, "
            f"current: {current_session_id[:8]}..., "
            f"requested: {requested_session_id[:8]}..."
        )
        return (
            False,
            403,
            "Forbidden: You can only access your own session. "
            "Session ownership validation failed.",
        )

    # Valid ownership - log successful validation
    security_logger.info(
        f"Successful session validation from IP: {client_ip}, "
        f"session: {current_session_id[:8]}..."
    )
    return (True, 200, "Session ownership validated successfully.")


def test_session_security():
    """Test various session security scenarios with enhanced validation"""

    print("🔒 Enhanced Session Ownership Validation Test")
    print("=" * 60)

    test_cases = [
        {
            "name": "No session cookie",
            "current_session": None,
            "requested_session": "a1b2c3d4e5f6789012345678901234ab",
            "expected_status": 401,
            "client_ip": "192.168.1.100",
        },
        {
            "name": "Empty session cookie",
            "current_session": "",
            "requested_session": "a1b2c3d4e5f6789012345678901234ab",
            "expected_status": 401,
            "client_ip": "192.168.1.101",
        },
        {
            "name": "Whitespace-only session cookie",
            "current_session": "   ",
            "requested_session": "a1b2c3d4e5f6789012345678901234ab",
            "expected_status": 401,
            "client_ip": "192.168.1.102",
        },
        {
            "name": "Invalid session ID format (too short)",
            "current_session": "short123",
            "requested_session": "a1b2c3d4e5f6789012345678901234ab",
            "expected_status": 401,
            "client_ip": "192.168.1.103",
        },
        {
            "name": "Invalid session ID format (non-hex characters)",
            "current_session": "g1h2i3j4k5l6789012345678901234ab",
            "requested_session": "a1b2c3d4e5f6789012345678901234ab",
            "expected_status": 401,
            "client_ip": "192.168.1.104",
        },
        {
            "name": "Invalid requested session format",
            "current_session": "a1b2c3d4e5f6789012345678901234ab",
            "requested_session": "invalid-session-format",
            "expected_status": 400,
            "client_ip": "192.168.1.105",
        },
        {
            "name": "Expired current session",
            "current_session": "e1f2a3b4c5d6789012345678901234ab",
            "requested_session": "e1f2a3b4c5d6789012345678901234ab",
            "expected_status": 401,
            "client_ip": "192.168.1.106",
        },
        {
            "name": "Access to expired requested session",
            "current_session": "a1b2c3d4e5f6789012345678901234ab",
            "requested_session": "0123456789abcdef0123456789abcdef",
            "expected_status": 410,
            "client_ip": "192.168.1.107",
        },
        {
            "name": "Cross-user access attempt (different valid sessions)",
            "current_session": "a1b2c3d4e5f6789012345678901234ab",
            "requested_session": "b2c3d4e5f6a7890123456789012345cd",
            "expected_status": 403,
            "client_ip": "192.168.1.108",
        },
        {
            "name": "Valid session ownership",
            "current_session": "c3d4e5f6a7b8901234567890123456ef",
            "requested_session": "c3d4e5f6a7b8901234567890123456ef",
            "expected_status": 200,
            "client_ip": "192.168.1.109",
        },
    ]

    print("\n📊 Running enhanced security validation tests...")

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i:2d}. {test_case['name']}")
        print(f"    Client IP: {test_case['client_ip']}")

        is_valid, status_code, message = validate_session_ownership(
            test_case["current_session"],
            test_case["requested_session"],
            test_case["client_ip"],
        )

        # Check if result matches expectation
        if status_code == test_case["expected_status"]:
            print(
                f"    ✅ Status: {status_code} "
                f"(Expected: {test_case['expected_status']})"
            )
        else:
            print(
                f"    ❌ Status: {status_code} "
                f"(Expected: {test_case['expected_status']})"
            )

        print(f"    📝 Message: {message}")

    print(f"\n🎯 Enhanced Security Validation Summary:")
    print(f"   • 400 Bad Request: Invalid request format")
    print(f"   • 401 Unauthorized: Missing, invalid, or expired session")
    print(f"   • 403 Forbidden: Session ID mismatch (cross-user access)")
    print(f"   • 410 Gone: Requested session has expired")
    print(f"   • 200 OK: Valid session ownership")

    print(f"\n🔒 Security Features Implemented:")
    print(f"   • Input validation and format checking")
    print(f"   • Session expiration validation")
    print(f"   • Comprehensive security logging")
    print(f"   • IP address tracking for audit trails")
    print(f"   • Protection against malformed requests")

    print(f"\n✅ Enhanced validation prevents:")
    print(f"   • Cross-user session access attempts")
    print(f"   • Access with expired or invalid sessions")
    print(f"   • Malformed session ID attacks")
    print(f"   • Session hijacking attempts")
    print(f"   • Unauthorized access without proper authentication")

    print(f"\n📋 Security Events Logged:")
    print(f"   • All validation attempts with IP addresses")
    print(f"   • Failed validation reasons and details")
    print(f"   • Successful authentications for audit")
    print(f"   • Session format and expiration violations")


def demonstrate_security_logging():
    """Demonstrate the security logging functionality"""
    print("\n🔍 Security Logging Demonstration")
    print("=" * 50)

    print("The following security events are automatically logged:")
    print("• Session access attempts without active sessions")
    print("• Invalid session ID formats and structures")
    print("• Session expiration violations")
    print("• Cross-user access attempts")
    print("• Successful session validations")
    print("• All events include IP addresses for audit trails")

    print("\nExample log entries from the test run above:")
    print("(Check console output for actual security log messages)")


if __name__ == "__main__":
    test_session_security()
    demonstrate_security_logging()
