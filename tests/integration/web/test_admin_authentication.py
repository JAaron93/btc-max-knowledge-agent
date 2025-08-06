#!/usr/bin/env python3
"""
Tests for Admin Authentication System
"""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import path is configured in tests/conftest.py; keep imports at top.
from src.web.admin_auth import AdminAuthenticator
from src.web.admin_router import admin_router

# Import shared password hashing utility from scripts directory without sys.path hacks
project_root = Path(__file__).resolve().parents[1]
scripts_path = project_root / "scripts"
spec = importlib.util.spec_from_file_location(
    "generate_admin_hash", scripts_path / "generate_admin_hash.py"
)
generate_admin_hash = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(generate_admin_hash)
hash_password = getattr(generate_admin_hash, "hash_password")


class TestAdminAuthenticator:
    """Test admin authentication functionality"""

    def setup_method(self):
        """Set up test authenticator"""
        # Create test authenticator with known credentials using shared utility
        test_password_hash = hash_password("admin123")

        with patch.dict(
            "os.environ",
            {
                "ADMIN_USERNAME": "test_admin",
                "ADMIN_PASSWORD_HASH": test_password_hash,
                "ADMIN_SECRET_KEY": (
                    "test_secret_key_64_hex_chars_representing_32_bytes_total"
                ),
            },
            clear=False,
        ):
            self.authenticator = AdminAuthenticator()

    def test_password_verification_through_authentication(self):
        """Test password verification through public authentication."""
        # Test with correct credentials - should succeed
        token = self.authenticator.authenticate_admin(
            "test_admin", "admin123", "192.168.1.1"
        )
        assert token is not None
        assert len(token) > 20
        assert token in self.authenticator.active_sessions

        # Clean up the session
        self.authenticator.revoke_admin_session(token, "192.168.1.1")

        # Test with incorrect password - should fail
        token = self.authenticator.authenticate_admin(
            "test_admin", "wrong_password", "192.168.1.1"
        )
        assert token is None

        # Test with incorrect username - should fail
        token = self.authenticator.authenticate_admin(
            "wrong_user", "admin123", "192.168.1.1"
        )
        assert token is None

    def test_admin_authentication_success(self):
        """Test successful admin authentication"""
        token = self.authenticator.authenticate_admin(
            "test_admin", "admin123", "192.168.1.1"
        )

        assert token is not None
        assert len(token) > 20  # Should be a substantial token
        assert token in self.authenticator.active_sessions

    def test_admin_authentication_failure(self):
        """Test failed admin authentication"""
        token = self.authenticator.authenticate_admin(
            "test_admin", "wrong_password", "192.168.1.1"
        )

        assert token is None

    def test_session_validation_success(self):
        """Test successful session validation"""
        # Create a session first
        token = self.authenticator.authenticate_admin(
            "test_admin", "admin123", "192.168.1.1"
        )

        # Validate the session
        is_valid = self.authenticator.validate_admin_session(token, "192.168.1.1")
        assert is_valid

    def test_session_validation_invalid_token(self):
        """Test session validation with invalid token"""
        is_valid = self.authenticator.validate_admin_session(
            "invalid_token", "192.168.1.1"
        )
        assert not is_valid

    def test_session_expiry(self):
        """Test session expiry functionality"""
        # Create a session
        token = self.authenticator.authenticate_admin(
            "test_admin", "admin123", "192.168.1.1"
        )

        # Use the public method to simulate expiry
        # Directly manipulate session data for testing purposes
        self.authenticator.active_sessions[token][
            "expires_at"
        ] = datetime.now() - timedelta(hours=1)

        # Validation should fail
        is_valid = self.authenticator.validate_admin_session(token, "192.168.1.1")
        assert not is_valid

        # Session should be removed after validation attempt
        assert token not in self.authenticator.active_sessions

    def test_session_revocation(self):
        """Test session revocation"""
        # Create a session
        token = self.authenticator.authenticate_admin(
            "test_admin", "admin123", "192.168.1.1"
        )

        # Revoke the session
        revoked = self.authenticator.revoke_admin_session(token, "192.168.1.1")
        assert revoked

        # Session should be removed
        assert token not in self.authenticator.active_sessions

        # Revoking again should return False
        revoked = self.authenticator.revoke_admin_session(token, "192.168.1.1")
        assert not revoked

    def test_session_cleanup(self):
        """Test cleanup of expired sessions"""
        # Create multiple sessions
        tokens = []
        for i in range(3):
            token = self.authenticator.authenticate_admin(
                "test_admin", "admin123", f"192.168.1.{i}"
            )
            tokens.append(token)

        # Expire some sessions using the public method
        # Directly manipulate session data for testing purposes
        self.authenticator.active_sessions[tokens[0]][
            "expires_at"
        ] = datetime.now() - timedelta(hours=1)
        self.authenticator.active_sessions[tokens[1]][
            "expires_at"
        ] = datetime.now() - timedelta(hours=1)

        # Run cleanup
        expired_count = self.authenticator.cleanup_expired_sessions()

        # Should have cleaned up 2 expired sessions
        assert expired_count == 2
        assert len(self.authenticator.active_sessions) == 1
        assert tokens[2] in self.authenticator.active_sessions

    def test_admin_stats(self):
        """Test admin statistics"""
        # Create some sessions
        for i in range(2):
            self.authenticator.authenticate_admin(
                "test_admin", "admin123", f"192.168.1.{i}"
            )

        stats = self.authenticator.get_admin_stats()

        assert stats["active_admin_sessions"] == 2
        assert "session_timeout_minutes" in stats
        assert "token_expiry_hours" in stats
        assert len(stats["sessions"]) == 2
        assert "rate_limiting" in stats

    def test_rate_limiting_through_authentication(self):
        """Test rate limiting functionality through public interface"""
        test_ip = "192.168.1.100"

        # Make multiple failed authentication attempts
        for i in range(6):  # Exceed the limit of 5
            token = self.authenticator.authenticate_admin(
                "test_admin", "wrong_password", test_ip
            )
            assert token is None

        # Check that IP is now locked out
        stats = self.authenticator.get_admin_stats()
        rate_limiting = stats["rate_limiting"]

        # Should have locked IPs or failed attempts recorded
        assert (
            len(rate_limiting["locked_ips"]) > 0
            or len(rate_limiting["failed_attempts"]) > 0
        )

        # Even correct password should fail due to lockout
        token = self.authenticator.authenticate_admin("test_admin", "admin123", test_ip)
        assert token is None

        # Test manual unlock
        unlocked = self.authenticator.unlock_ip(test_ip)
        assert unlocked

        # Should be able to authenticate after unlock
        token = self.authenticator.authenticate_admin("test_admin", "admin123", test_ip)
        assert token is not None


class TestAdminRouter:
    """Test admin router endpoints"""

    def setup_method(self):
        """Set up test client"""
        # Create test app with admin router
        app = FastAPI()
        app.include_router(admin_router)
        self.client = TestClient(app)

        # Mock the bitcoin_service
        self.mock_bitcoin_service = Mock()
        self.mock_session_manager = Mock()
        self.mock_bitcoin_service.session_manager = self.mock_session_manager

        # Patch the bitcoin_service import
        self.bitcoin_service_patcher = patch(
            "src.web.admin_router.bitcoin_service", self.mock_bitcoin_service
        )
        self.bitcoin_service_patcher.start()

    def teardown_method(self):
        """Clean up patches"""
        self.bitcoin_service_patcher.stop()

    def test_admin_login_success(self):
        """Test successful admin login"""
        with patch("src.web.admin_router.get_admin_authenticator") as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.authenticate_admin.return_value = "test_token_123"
            mock_get_auth.return_value = mock_authenticator

            response = self.client.post(
                "/admin/login",
                json={"username": "admin", "password": "admin123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "test_token_123"
            assert data["token_type"] == "bearer"

    def test_admin_login_failure(self):
        """Test failed admin login"""
        with patch("src.web.admin_router.get_admin_authenticator") as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.authenticate_admin.return_value = None
            mock_get_auth.return_value = mock_authenticator

            response = self.client.post(
                "/admin/login",
                json={"username": "admin", "password": "wrong_password"},
            )

            assert response.status_code == 401
            assert "Invalid admin credentials" in response.json()["detail"]

    def test_protected_endpoint_without_auth(self):
        """Test accessing protected endpoint without authentication"""
        response = self.client.get("/admin/sessions/stats")

        assert response.status_code == 401
        assert "authorization header" in response.json()["detail"].lower()

    def test_protected_endpoint_with_invalid_token(self):
        """Test accessing protected endpoint with invalid token"""
        with patch("src.web.admin_auth.get_admin_authenticator") as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.validate_admin_session.return_value = False
            mock_get_auth.return_value = mock_authenticator

            response = self.client.get(
                "/admin/sessions/stats",
                headers={"Authorization": "Bearer invalid_token"},
            )

            assert response.status_code == 403
            assert "Invalid or expired admin session" in response.json()["detail"]

    def test_protected_endpoint_with_valid_token(self):
        """Test accessing protected endpoint with valid token"""
        with patch("src.web.admin_auth.get_admin_authenticator") as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.validate_admin_session.return_value = True
            mock_get_auth.return_value = mock_authenticator

            # Mock session manager stats
            self.mock_session_manager.get_session_stats.return_value = {
                "active_sessions": 5,
                "total_conversations": 10,
            }

            response = self.client.get(
                "/admin/sessions/stats",
                headers={"Authorization": "Bearer valid_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "session_statistics" in data
            assert data["admin_access"]

    def test_admin_logout(self):
        """Test admin logout"""
        with patch("src.web.admin_router.get_admin_authenticator") as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.validate_admin_session.return_value = True
            mock_authenticator.revoke_admin_session.return_value = True
            mock_get_auth.return_value = mock_authenticator

            response = self.client.post(
                "/admin/logout",
                headers={"Authorization": "Bearer valid_token"},
            )

            assert response.status_code == 200
            assert "revoked successfully" in response.json()["message"]

    def test_force_delete_session(self):
        """Test admin force delete session"""
        with patch("src.web.admin_auth.get_admin_authenticator") as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.validate_admin_session.return_value = True
            mock_get_auth.return_value = mock_authenticator

            # Mock session manager
            self.mock_session_manager.remove_session.return_value = True

            response = self.client.delete(
                "/admin/sessions/test_session_123",
                headers={"Authorization": "Bearer valid_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "force-deleted successfully" in data["message"]
            assert data["admin_access"]


if __name__ == "__main__":
    pytest.main([__file__])
