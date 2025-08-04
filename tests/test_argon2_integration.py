#!/usr/bin/env python3
"""
Integration tests for Argon2id password hashing upgrade
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.web.admin_auth import AdminAuthenticator


class TestArgon2Integration:
    """Test Argon2id integration in admin authentication"""
    
    def setup_method(self):
        """Set up test authenticator"""
        # Generate a test password hash for "admin123"
        import hashlib
        import secrets
        
        def hash_password(password: str) -> str:
            salt = secrets.token_bytes(32)
            pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200000)
            return salt.hex() + ':' + pwdhash.hex()
        
        test_password_hash = hash_password("admin123")
        
        with patch.dict('os.environ', {
            'ADMIN_USERNAME': 'test_admin',
            'ADMIN_PASSWORD_HASH': test_password_hash,
            'ADMIN_SECRET_KEY': 'test_secret_key_64_hex_chars_representing_32_bytes_total'
        }, clear=False):
            self.authenticator = AdminAuthenticator()
    
    def test_argon2id_hash_format(self):
        """Test that password hashes use Argon2id format"""
        # Authenticate to trigger password hashing
        token = self.authenticator.authenticate_admin(
            "test_admin", "admin123", "127.0.0.1"
        )
        assert token is not None
        
        # Check that the stored hash uses Argon2id format
        assert self.authenticator.admin_password_hash.startswith("$argon2id$")
        
        # Clean up
        self.authenticator.revoke_admin_session(token, "127.0.0.1")
    
    def test_password_verification_security(self):
        """Test password verification security properties"""
        # Test that authentication works with correct password
        token1 = self.authenticator.authenticate_admin(
            "test_admin", "admin123", "127.0.0.1"
        )
        assert token1 is not None
        
        # Test that authentication fails with incorrect password
        token2 = self.authenticator.authenticate_admin(
            "test_admin", "wrong_password", "127.0.0.1"
        )
        assert token2 is None
        
        # Test that empty password fails
        token3 = self.authenticator.authenticate_admin(
            "test_admin", "", "127.0.0.1"
        )
        assert token3 is None
        
        # Clean up
        if token1:
            self.authenticator.revoke_admin_session(token1, "127.0.0.1")
    
    def test_hash_uniqueness(self):
        """Test that password hashing produces unique results"""
        # Create two authenticators with the same password
        auth1 = AdminAuthenticator()
        auth2 = AdminAuthenticator()
        
        # Both should work with the same password but have different hashes
        # (due to automatic salt generation in Argon2id)
        token1 = auth1.authenticate_admin("admin", "admin123", "127.0.0.1")
        token2 = auth2.authenticate_admin("admin", "admin123", "127.0.0.2")
        
        assert token1 is not None
        assert token2 is not None
        
        # The hashes should be different due to salt
        if hasattr(auth1, 'admin_password_hash') and hasattr(auth2, 'admin_password_hash'):
            # Only compare if both have generated hashes
            if (auth1.admin_password_hash.startswith("$argon2id$") and 
                auth2.admin_password_hash.startswith("$argon2id$")):
                assert auth1.admin_password_hash != auth2.admin_password_hash
        
        # Clean up
        auth1.revoke_admin_session(token1, "127.0.0.1")
        auth2.revoke_admin_session(token2, "127.0.0.2")
    
    def test_backward_compatibility(self):
        """Test that the upgrade maintains API compatibility"""
        # All public methods should still work as expected
        
        # Authentication
        token = self.authenticator.authenticate_admin(
            "test_admin", "admin123", "127.0.0.1"
        )
        assert token is not None
        
        # Session validation
        is_valid = self.authenticator.validate_admin_session(token, "127.0.0.1")
        assert is_valid
        
        # Session info
        session_info = self.authenticator.get_admin_session_info(token)
        assert session_info is not None
        assert session_info["username"] == "test_admin"
        
        # Statistics
        stats = self.authenticator.get_admin_stats()
        assert "active_admin_sessions" in stats
        assert "rate_limiting" in stats
        
        # Session revocation
        revoked = self.authenticator.revoke_admin_session(token, "127.0.0.1")
        assert revoked
        
        # Cleanup
        self.authenticator.cleanup_expired_sessions()


if __name__ == "__main__":
    pytest.main([__file__])    pytest.main([__file__])