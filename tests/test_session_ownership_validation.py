#!/usr/bin/env python3
"""
Tests for Session Ownership Validation
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add project root to path (consider using pytest fixtures for better isolation)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.web.bitcoin_assistant_api import app
from src.web.session_manager import SessionManager, SessionData


class TestSessionOwnershipValidation:
    """Test session ownership validation in API endpoints"""
    
    def setup_method(self):
        """Set up test client and mock services"""
        self.client = TestClient(app)
        self.mock_session_manager = Mock(spec=SessionManager)
        
        # Mock the bitcoin_service
        self.mock_bitcoin_service = Mock()
        self.mock_bitcoin_service.session_manager = self.mock_session_manager
        
        # Patch the global bitcoin_service
        self.bitcoin_service_patcher = patch('src.web.bitcoin_assistant_api.bitcoin_service', self.mock_bitcoin_service)
        self.bitcoin_service_patcher.start()
    
    def teardown_method(self):
        """Clean up patches"""
        self.bitcoin_service_patcher.stop()
    
    def test_delete_session_without_cookie(self):
        """Test that deleting a session without a cookie returns 401"""
        response = self.client.delete("/session/test-session-123")
        
        assert response.status_code == 401
        assert "No active session found" in response.json()["detail"]
    
    def test_delete_session_with_wrong_session_id(self):
        """Test that deleting a different session returns 403"""
        # User has session A but tries to delete session B
        user_session_id = "user-session-123"
        target_session_id = "other-session-456"
        
        response = self.client.delete(
            f"/session/{target_session_id}",
            cookies={"btc_assistant_session": user_session_id}
        )
        
        assert response.status_code == 403
        assert "Forbidden: You can only delete your own session" in response.json()["detail"]
    
    def test_delete_session_with_valid_ownership(self):
        """Test that deleting own session works correctly"""
        session_id = "valid-session-123"
        
        # Mock session exists and removal succeeds
        mock_session = Mock(spec=SessionData)
        self.mock_session_manager.get_session.return_value = mock_session
        self.mock_session_manager.remove_session.return_value = True
        
        response = self.client.delete(
            f"/session/{session_id}",
            cookies={"btc_assistant_session": session_id}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Session deleted successfully"
        assert response.json()["session_id"] == session_id
        
        # Verify the session manager was called correctly
        self.mock_session_manager.get_session.assert_called_once_with(session_id)
        self.mock_session_manager.remove_session.assert_called_once_with(session_id)
    
    def test_delete_nonexistent_session(self):
        """Test that deleting a non-existent session returns 404"""
        session_id = "nonexistent-session-123"
        
        # Mock session doesn't exist
        self.mock_session_manager.get_session.return_value = None
        
        response = self.client.delete(
            f"/session/{session_id}",
            cookies={"btc_assistant_session": session_id}
        )
        
        assert response.status_code == 404
        assert "Session not found or already expired" in response.json()["detail"]
    
    def test_get_session_info_without_cookie(self):
        """Test that getting session info without a cookie returns 401"""
        response = self.client.get("/session/test-session-123")
        
        assert response.status_code == 401
        assert "No active session found" in response.json()["detail"]
    
    def test_get_session_info_with_wrong_session_id(self):
        """Test that getting info for a different session returns 403"""
        user_session_id = "user-session-123"
        target_session_id = "other-session-456"
        
        response = self.client.get(
            f"/session/{target_session_id}",
            cookies={"btc_assistant_session": user_session_id}
        )
        
        assert response.status_code == 403
        assert "Forbidden: You can only access your own session information" in response.json()["detail"]
    
    def test_get_session_info_with_valid_ownership(self):
        """Test that getting own session info works correctly"""
        session_id = "valid-session-123"
        
        # Mock session data
        mock_session = Mock(spec=SessionData)
        mock_session.to_dict.return_value = {"session_id": session_id, "created_at": "2024-01-01"}
        mock_session.conversation_history = [{"question": "test", "answer": "test"}]
        mock_session.get_conversation_context.return_value = []
        
        self.mock_session_manager.get_session.return_value = mock_session
        
        response = self.client.get(
            f"/session/{session_id}",
            cookies={"btc_assistant_session": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_info" in data
        assert "conversation_history" in data
        assert "conversation_context" in data
        
        # Verify the session manager was called correctly
        self.mock_session_manager.get_session.assert_called_once_with(session_id)
    
    def test_get_session_info_nonexistent_session(self):
        """Test that getting info for a non-existent session returns 404"""
        session_id = "nonexistent-session-123"
        
        # Mock session doesn't exist
        self.mock_session_manager.get_session.return_value = None
        
        response = self.client.get(
            f"/session/{session_id}",
            cookies={"btc_assistant_session": session_id}
        )
        
        assert response.status_code == 404
        assert "Session not found or expired" in response.json()["detail"]
    
    def test_session_ownership_prevents_cross_user_access(self):
        """Test that users cannot access each other's sessions"""
        alice_session = "alice-session-123"
        bob_session = "bob-session-456"
        
        # Alice tries to access Bob's session
        response = self.client.get(
            f"/session/{bob_session}",
            cookies={"btc_assistant_session": alice_session}
        )
        
        assert response.status_code == 403
        
        # Alice tries to delete Bob's session
        response = self.client.delete(
            f"/session/{bob_session}",
            cookies={"btc_assistant_session": alice_session}
        )
        
        assert response.status_code == 403
    
    def test_session_ownership_allows_self_access(self):
        """Test that users can access their own sessions"""
        session_id = "user-session-123"
        
        # Mock session exists
        mock_session = Mock(spec=SessionData)
        mock_session.to_dict.return_value = {"session_id": session_id}
        mock_session.conversation_history = []
        mock_session.get_conversation_context.return_value = []
        self.mock_session_manager.get_session.return_value = mock_session
        self.mock_session_manager.remove_session.return_value = True
        
        # User can get their own session info
        response = self.client.get(
            f"/session/{session_id}",
            cookies={"btc_assistant_session": session_id}
        )
        assert response.status_code == 200
        
        # User can delete their own session
        response = self.client.delete(
            f"/session/{session_id}",
            cookies={"btc_assistant_session": session_id}
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__])