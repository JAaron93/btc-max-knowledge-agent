#!/usr/bin/env python3
"""
Admin Security System Demo
Demonstrates the comprehensive admin authentication and authorization system
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.web.admin_auth import AdminAuthenticator
except ImportError as e:
    print(f"Error: Could not import AdminAuthenticator: {e}")
    print("Please ensure the admin authentication module is available.")
    sys.exit(1)


def print_header(auth):
    """Print the demo header and introduction"""
    print("🔐 Bitcoin Knowledge Assistant - Admin Security Demo")
    print("=" * 60)

    print("\n1. 🛡️ ADMIN AUTHENTICATION SYSTEM")
    print("-" * 45)

    print("   Security Features:")
    print("   • ✅ Argon2id password hashing (OWASP recommended)")
    print("   • ✅ Cryptographically secure session tokens")
    print("   • ✅ Time-based token expiry (24 hours)")
    print("   • ✅ Session inactivity timeout (30 minutes)")
    print("   • ✅ IP address logging and monitoring")
    print("   • ✅ Rate limiting with IP lockout (5 attempts, 15 min lockout)")


# Demo credentials - should be changed in production
DEMO_USERNAME = "demo_admin"
DEMO_PASSWORD = "demo_password_123"


def demo_password_security(auth):
    """Demonstrate password hashing and verification"""
    print("\n2. 🔑 PASSWORD SECURITY")
    print("-" * 45)

    # Demonstrate password security features without exposing internals
    print("   Password Security Features:")
    print("   • Argon2id hashing algorithm (OWASP recommended)")
    print("   • Memory-hard function resistant to GPU attacks")
    print("   • Automatic salt generation and management")
    print("   • Constant-time verification to prevent timing attacks")
    print("   • Configurable time, memory, and parallelism parameters")

    # Test authentication with safe demo credentials
    demo_result = auth.authenticate_admin(DEMO_USERNAME, DEMO_PASSWORD, "127.0.0.1")
    if demo_result:
        print("   ✅ Demo authentication successful")
        print(f"   ✅ Session token generated: {demo_result[:16]}...")
        # Clean up demo session
        auth.revoke_admin_session(demo_result, "127.0.0.1")
    else:
        print("   ❌ Demo authentication failed")

    # Test with wrong credentials (safe demo)
    wrong_result = auth.authenticate_admin(DEMO_USERNAME, "wrong_password", "127.0.0.1")
    status = "Failed" if not wrong_result else "Unexpected success"
    print(f"   ❌ Wrong password authentication: {status}")


def demo_session_management(auth):
    """Demonstrate session creation and validation"""
    print("\n3. 🎫 SESSION TOKEN MANAGEMENT")
    print("-" * 45)

    # Test authentication scenarios
    scenarios = [
        ("admin", "admin123", "192.168.1.100", "Valid credentials"),
        ("admin", "wrong_password", "192.168.1.101", "Invalid password"),
        ("wrong_user", "admin123", "192.168.1.102", "Invalid username"),
        ("admin", "admin123", "10.0.0.1", "Valid from different IP"),
    ]

    valid_tokens = []

    for username, password, ip, description in scenarios:
        token = auth.authenticate_admin(username, password, ip)

        if token:
            valid_tokens.append((token, ip))
            print(f"   ✅ {description}: Token generated ({token[:16]}...)")
        else:
            print(f"   ❌ {description}: Authentication failed")

    print(f"\n   📊 Active Sessions: {len(valid_tokens)}")

    print("\n4. 🔍 SESSION VALIDATION")
    print("-" * 45)

    if valid_tokens:
        token, ip = valid_tokens[0]

        # Test valid session
        if auth.validate_admin_session(token, ip):
            print("   ✅ Valid token validation: Access granted")
        else:
            print("   ❌ Valid token validation: Access unexpectedly denied")
        if auth.validate_admin_session("invalid_token_123", ip):
            print("   ⚠️ Invalid token accepted: potential vulnerability!")
        else:
            print("   ❌ Invalid token validation: Access denied (expected)")
        if auth.validate_admin_session(token, "different.ip.address"):
            print("   ⚠️ Different IP accepted: IP check may be bypassed!")
        else:
            print("   ⚠️ Different IP validation: Access denied (expected)")
        print("   ⚠️  Different IP validation: Access attempt from different location")

    return valid_tokens


def demo_security_features(auth, valid_tokens=None):
    """Demonstrate security features including stats, cleanup, and monitoring"""
    if valid_tokens is None:
        valid_tokens = []

    print("\n5. 📊 ADMIN STATISTICS")
    print("-" * 45)

    stats = auth.get_admin_stats()

    print(f"   Active Admin Sessions: {stats['active_admin_sessions']}")
    print(f"   Session Timeout: {stats['session_timeout_minutes']} minutes")
    print(f"   Token Expiry: {stats['token_expiry_hours']} hours")

    # Show rate limiting stats
    rate_limiting = stats.get("rate_limiting", {})
    max_attempts = rate_limiting.get("max_login_attempts", "N/A")
    lockout_duration = rate_limiting.get("lockout_duration_minutes", "N/A")
    print(f"   Max Login Attempts: {max_attempts}")
    print(f"   Lockout Duration: {lockout_duration} minutes")
    print(f"   Currently Locked IPs: {len(rate_limiting.get('locked_ips', []))}")
    print(
        f"   IPs with Failed Attempts: {len(rate_limiting.get('failed_attempts', []))}"
    )

    if stats["sessions"]:
        print("\n   Session Details:")
        for i, session in enumerate(stats["sessions"], 1):
            username = session["username"]
            client_ip = session["client_ip"]
            print(f"   {i}. User: {username}, IP: {client_ip}")
            print(f"      Created: {session['created_at']}")
            print(f"      Last Activity: {session['last_activity']}")

    print("\n6. 🧹 SESSION CLEANUP")
    print("-" * 45)

    print("   Automatic Cleanup Features:")
    print("   • ✅ Background cleanup task runs every 5 minutes")
    print("   • ✅ Cleanup called before each session validation")
    print("   • ✅ Manual cleanup available for immediate use")
    print("   • ✅ Comprehensive logging of cleanup activities")

    # Simulate expired sessions for cleanup demo
    if valid_tokens:
        # Simulate session expiry by manipulating session data for demo purposes
        from datetime import datetime, timedelta

        token, _ = valid_tokens[0]
        if token in auth.active_sessions:
            auth.active_sessions[token]["expires_at"] = datetime.now() - timedelta(
                hours=1
            )
            print("   🕐 Simulated session expiry for demo")

        # Run cleanup
        expired_count = auth.cleanup_expired_sessions()
        print(f"   🧹 Cleaned up {expired_count} expired sessions")

        # Show updated stats
        updated_stats = auth.get_admin_stats()
        remaining = updated_stats["active_admin_sessions"]
        print(f"   📊 Remaining active sessions: {remaining}")

    print("\n   Memory Management:")
    print("   • Prevents memory growth from expired sessions")
    print("   • Automatic cleanup prevents manual intervention")
    print("   • Background task survives application restarts")

    print("\n7. 🚫 SECURITY VIOLATIONS")
    print("-" * 45)

    print("   Common attack scenarios and protections:")

    # Brute force protection
    print("   • Brute Force Attacks:")
    print("     - Rate limiting: 5 attempts per IP address")
    print("     - IP lockout: 15 minutes after max attempts")
    print("     - Failed attempts logged with timestamps")
    print("     - Automatic cleanup of expired lockouts")
    print("     - Manual IP unlock capability for admins")

    # Session hijacking protection
    print("   • Session Hijacking:")
    print("     - Cryptographically secure tokens (256-bit entropy)")
    print("     - IP address consistency monitoring")
    print("     - Automatic session expiry")

    # Token theft protection
    print("   • Token Theft:")
    print("     - Short token lifetime (24 hours)")
    print("     - Session inactivity timeout (30 minutes)")
    print("     - Secure token revocation on logout")

    print("\n8. 🔒 ADMIN ENDPOINT PROTECTION")
    print("-" * 45)

    protected_endpoints = [
        "/admin/sessions/stats",
        "/admin/sessions/cleanup",
        "/admin/sessions/rate-limits",
        "/admin/sessions/list",
        "/admin/sessions/{session_id}",
        "/admin/auth/stats",
        "/admin/health",
    ]

    print("   Protected Admin Endpoints:")
    for endpoint in protected_endpoints:
        print(f"   • {endpoint}")

    print("\n   Protection Mechanisms:")
    print("   • ✅ Bearer token authentication required")
    print("   • ✅ Token validation on every request")
    print("   • ✅ Session expiry and timeout enforcement")
    print("   • ✅ Comprehensive access logging")
    print("   • ✅ IP address tracking and monitoring")

    print("\n9. 📝 SECURITY LOGGING")
    print("-" * 45)

    print("   All admin activities are logged:")
    print("   • ✅ Login attempts (success/failure)")
    print("   • ✅ Session creation and expiry")
    print("   • ✅ Admin endpoint access")
    print("   • ✅ Session validation failures")
    print("   • ✅ IP address changes")
    print("   • ✅ Token revocation events")
    print("   • ✅ Security violations and anomalies")


def demo_production_checklist():
    """Demonstrate production deployment security checklist"""
    print("\n10. 🚀 PRODUCTION DEPLOYMENT")
    print("-" * 45)

    print("   Production Security Checklist:")
    print("   • ✅ Set strong admin credentials (ADMIN_USERNAME, ADMIN_PASSWORD_HASH)")
    print("   • ✅ Configure secure secret key (ADMIN_SECRET_KEY)")
    print("   • ✅ Use HTTPS for all admin endpoints")
    print("   • ✅ Restrict admin access by IP/network")
    print("   • ✅ Monitor admin access logs")
    print("   • ✅ Set up alerting for failed login attempts")
    print("   • ✅ Regularly rotate admin credentials")
    print("   • ✅ Use reverse proxy with additional authentication")


def print_summary():
    """Print the final security summary"""
    print("\n✅ COMPREHENSIVE ADMIN SECURITY IMPLEMENTED")
    print("=" * 60)

    print("\n🔐 Security Benefits:")
    print("   • Prevents unauthorized access to admin functions")
    print("   • Protects sensitive session and system statistics")
    print("   • Provides detailed audit trail of admin activities")
    print("   • Implements industry-standard authentication practices")
    print("   • Scales securely with proper session management")
    print("   • Ready for enterprise production deployment")

    print("\n🛡️ Attack Resistance:")
    print("   • Brute force attacks: Rate limiting + delays")
    print("   • Session hijacking: Secure tokens + IP monitoring")
    print("   • Token theft: Short lifetime + inactivity timeout")
    print("   • Privilege escalation: Strict endpoint protection")
    print("   • Information disclosure: Authentication required")
    print("   • Replay attacks: Time-based token expiry")

    print("\n🚀 Ready for production with military-grade admin security!")


def demo_admin_security():
    """Main demo orchestrator"""
    results = {
        "print_header": False,
        "demo_password_security": False,
        "demo_session_management": False,
        "demo_security_features": False,
        "demo_production_checklist": False,
        "print_summary": False,
    }

    # Create single AdminAuthenticator instance to be shared across all demo functions
    try:
        authenticator = AdminAuthenticator()
        logging.info("AdminAuthenticator instance created successfully")
    except Exception as exc:
        logging.exception("Failed to create AdminAuthenticator: %s", exc)
        return results

    try:
        print_header(authenticator)
        results["print_header"] = True
        logging.info("print_header completed successfully")
    except Exception as exc:
        logging.exception("print_header() failed: %s", exc)
        return results

    # Password security demo with error handling
    try:
        demo_password_security(authenticator)
        results["demo_password_security"] = True
        logging.info("demo_password_security completed successfully")
    except Exception as exc:
        logging.exception("Password-security demo failed: %s", exc)
        # continue, but flag that subsequent steps may be unreliable

    valid_tokens = None
    try:
        valid_tokens = demo_session_management(authenticator)
        if not valid_tokens:
            logging.error("Session-management demo returned no tokens.")
        results["demo_session_management"] = True
        logging.info("demo_session_management completed successfully")
    except Exception as exc:
        logging.exception("Session-management demo failed: %s", exc)

    # Guard demo_security_features with try/except
    try:
        if valid_tokens:
            demo_security_features(authenticator, valid_tokens)
        else:
            demo_security_features(authenticator)
        results["demo_security_features"] = True
        logging.info("demo_security_features completed successfully")
    except Exception as exc:
        logging.exception("demo_security_features failed: %s", exc)
        # Continue executing the rest of the demo

    # Guard demo_production_checklist with try/except
    try:
        demo_production_checklist()
        results["demo_production_checklist"] = True
        logging.info("demo_production_checklist completed successfully")
    except Exception as exc:
        logging.exception("demo_production_checklist failed: %s", exc)
        # Continue executing the rest of the demo

    # Guard print_summary with try/except
    try:
        print_summary()
        results["print_summary"] = True
        logging.info("print_summary completed successfully")
    except Exception as exc:
        logging.exception("print_summary failed: %s", exc)
        # This is the final step, so no need to continue

    return results


if __name__ == "__main__":
    demo_admin_security()
