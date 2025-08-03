#!/usr/bin/env python3
"""
Tests for Admin Authentication System
"""

import pytest
import time
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.web.admin_auth import AdminAuthenticator, get_admin_authenticator
from src.web.admin_router import admin_router
from fastapi import FastAPI


class TestAdminAuthenticator:
    """Test admin authentication functionality"""
    
    def setup_method(self):
        """Set up test authenticator"""
        # Create test authenticator with known credentials
        with patch.dict('os.environ', {
            'ADMIN_USERNAME': 'test_admin',
            'ADMIN_PASSWORD_HASH': 'test_salt:test_hash',
            'ADMIN_SECRET_KEY': 'test_secret_key_32_characters_long'
        }):
            self.authenticator = AdminAuthenticator()
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123"
        
        # Hash password
        password_hash = self.authenticator._hash_password(password)
        
        # Verify correct password
        assert self.authenticator._verify_password(password, password_hash) == True
        
        # Verify incorrect password
        assert self.authenticator._verify_password("wrong_password", password_hash) == False
    
    def test_admin_authentication_success(self):
        """Test successful admin authentication"""
        # Mock password verification to return True
        with patch.object(self.authenticator, '_verify_password', return_value=True):
            token = self.authenticator.authenticate_admin("test_admin", "correct_password", "192.168.1.1")
            
            assert token is not None
            assert len(token) > 20  # Should be a substantial token
            assert token in self.authenticator.active_sessions
    
    def test_admin_authentication_failure(self):
        """Test failed admin authentication"""
        # Mock password verification to return False
        with patch.object(self.authenticator, '_verify_password', return_value=False):
            token = self.authenticator.authenticate_admin("test_admin", "wrong_password", "192.168.1.1")
            
            assert token is None
    
    def test_session_validation_success(self):
        """Test successful session validation"""
        # Create a session first
        with patch.object(self.authenticator, '_verify_password', return_value=True):
            token = self.authenticator.authenticate_admin("test_admin", "correct_password", "192.168.1.1")
        
        # Validate the session
        is_valid = self.authenticator.validate_admin_session(token, "192.168.1.1")
        assert is_valid == True
    
    def test_session_validation_invalid_token(self):
        """Test session validation with invalid token"""
        is_valid = self.authenticator.validate_admin_session("invalid_token", "192.168.1.1")
        assert is_valid == False
    
    def test_session_expiry(self):
        """Test session expiry functionality"""
        # Create a session
        with patch.object(self.authenticator, '_verify_password', return_value=True):
            token = self.authenticator.authenticate_admin("test_admin", "correct_password", "192.168.1.1")
        
        # Manually expire the session
        from datetime import datetime, timedelta
        self.authenticator.active_sessions[token]["expires_at"] = datetime.now() - timedelta(hours=1)
        
        # Validation should fail
        is_valid = self.authenticator.validate_admin_session(token, "192.168.1.1")
        assert is_valid == False
        
        # Session should be removed
        assert token not in self.authenticator.active_sessions
    
    def test_session_revocation(self):
        """Test session revocation"""
        # Create a session
        with patch.object(self.authenticator, '_verify_password', return_value=True):
            token = self.authenticator.authenticate_admin("test_admin", "correct_password", "192.168.1.1")
        
        # Revoke the session
        revoked = self.authenticator.revoke_admin_session(token, "192.168.1.1")
        assert revoked == True
        
        # Session should be removed
        assert token not in self.authenticator.active_sessions
        
        # Revoking again should return False
        revoked = self.authenticator.revoke_admin_session(token, "192.168.1.1")
        assert revoked == False
    
    def test_session_cleanup(self):
        """Test cleanup of expired sessions"""
        # Create multiple sessions
        tokens = []
        with patch.object(self.authenticator, '_verify_password', return_value=True):
            for i in range(3):
                token = self.authenticator.authenticate_admin("test_admin", "correct_password", f"192.168.1.{i}")
                tokens.append(token)
        
        # Expire some sessions
        from datetime import datetime, timedelta
        self.authenticator.active_sessions[tokens[0]]["expires_at"] = datetime.now() - timedelta(hours=1)
        self.authenticator.active_sessions[tokens[1]]["last_activity"] = datetime.now() - timedelta(hours=1)
        
        # Run cleanup
        expired_count = self.authenticator.cleanup_expired_sessions()
        
        # Should have cleaned up 2 expired sessions
        assert expired_count == 2
        assert len(self.authenticator.active_sessions) == 1
        assert tokens[2] in self.authenticator.active_sessions
    
    def test_admin_stats(self):
        """Test admin statistics"""
        # Create some sessions
        with patch.object(self.authenticator, '_verify_password', return_value=True):
            for i in range(2):
                self.authenticator.authenticate_admin("test_admin", "correct_password", f"192.168.1.{i}")
        
        stats = self.authenticator.get_admin_stats()
        
        assert stats["active_admin_sessions"] == 2
        assert "session_timeout_minutes" in stats
        assert "token_expiry_hours" in stats
        assert len(stats["sessions"]) == 2


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
        self.bitcoin_service_patcher = patch('src.web.admin_router.bitcoin_service', self.mock_bitcoin_service)
        self.bitcoin_service_patcher.start()
    
    def teardown_method(self):
        """Clean up patches"""
        self.bitcoin_service_patcher.stop()
    
    def test_admin_login_success(self):
        """Test successful admin login"""
        with patch('src.web.admin_router.get_admin_authenticator') as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.authenticate_admin.return_value = "test_token_123"
            mock_get_auth.return_value = mock_authenticator
            
            response = self.client.post("/admin/login", json={
                "username": "admin",
                "password": "admin123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "test_token_123"
            assert data["token_type"] == "bearer"
    
    def test_admin_login_failure(self):
        """Test failed admin login"""
        with patch('src.web.admin_router.get_admin_authenticator') as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.authenticate_admin.return_value = None
            mock_get_auth.return_value = mock_authenticator
            
            response = self.client.post("/admin/login", json={
                "username": "admin",
                "password": "wrong_password"
            })
            
            assert response.status_code == 401
            assert "Invalid admin credentials" in response.json()["detail"]
    
    def test_protected_endpoint_without_auth(self):
        """Test accessing protected endpoint without authentication"""
        response = self.client.get("/admin/sessions/stats")
        
        assert response.status_code == 401
        assert "authorization header" in response.json()["detail"].lower()
    
    def test_protected_endpoint_with_invalid_token(self):
        """Test accessing protected endpoint with invalid token"""
        with patch('src.web.admin_auth.get_admin_authenticator') as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.validate_admin_session.return_value = False
            mock_get_auth.return_value = mock_authenticator
            
            response = self.client.get(
                "/admin/sessions/stats",
                headers={"Authorization": "Bearer invalid_token"}
            )
            
            assert response.status_code == 403
            assert "Invalid or expired admin session" in response.json()["detail"]
    
    def test_protected_endpoint_with_valid_token(self):
        """Test accessing protected endpoint with valid token"""
        with patch('src.web.admin_auth.get_admin_authenticator') as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.validate_admin_session.return_value = True
            mock_get_auth.return_value = mock_authenticator
            
            # Mock session manager stats
            self.mock_session_manager.get_session_stats.return_value = {
                "active_sessions": 5,
                "total_conversations": 10
            }
            
            response = self.client.get(
                "/admin/sessions/stats",
                headers={"Authorization": "Bearer valid_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "session_statistics" in data
            assert data["admin_access"] == True
    
    def test_admin_logout(self):
        """Test admin logout"""
        with patch('src.web.admin_router.get_admin_authenticator') as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.validate_admin_session.return_value = True
            mock_authenticator.revoke_admin_session.return_value = True
            mock_get_auth.return_value = mock_authenticator
            
            response = self.client.post(
                "/admin/logout",
                headers={"Authorization": "Bearer valid_token"}
            )
            
            assert response.status_code == 200
            assert "revoked successfully" in response.json()["message"]
    
    def test_force_delete_session(self):
        """Test admin force delete session"""
        with patch('src.web.admin_auth.get_admin_authenticator') as mock_get_auth:
            mock_authenticator = Mock()
            mock_authenticator.validate_admin_session.return_value = True
            mock_get_auth.return_value = mock_authenticator
            
            # Mock session manager
            self.mock_session_manager.remove_session.return_value = True
            
            response = self.client.delete(
                "/admin/sessions/test_session_123",
                headers={"Authorization": "Bearer valid_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "force-deleted successfully" in data["message"]
            assert data["admin_access"] == True


if __name__ == "__main__":
    pytest.main([__file__])