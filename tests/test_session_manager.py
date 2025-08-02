#!/usr/bin/env python3
"""
Tests for Session Management
"""

import pytest
import time
from datetime import datetime, timedelta

from src.web.session_manager import SessionManager, SessionData, get_session_manager


class TestSessionData:
    """Test SessionData class"""
    
    def test_session_creation(self):
        """Test session data creation"""
        session_id = "test-session-123"
        session = SessionData(session_id)
        
        assert session.session_id == session_id
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
        assert session.conversation_history == []
        assert session.pinecone_thread_id is None
        assert session.tts_preferences['enabled'] is True
        assert session.tts_preferences['volume'] == 0.7
    
    def test_conversation_turn(self):
        """Test adding conversation turns"""
        session = SessionData("test-session")
        
        # Add first turn
        session.add_conversation_turn("What is Bitcoin?", "Bitcoin is a cryptocurrency", [])
        
        assert len(session.conversation_history) == 1
        turn = session.conversation_history[0]
        assert turn['question'] == "What is Bitcoin?"
        assert turn['answer'] == "Bitcoin is a cryptocurrency"
        assert turn['sources'] == []
        assert turn['turn_id'] == 1
        
        # Add second turn
        session.add_conversation_turn("How does mining work?", "Mining validates transactions", [{"source": "test"}])
        
        assert len(session.conversation_history) == 2
        turn = session.conversation_history[1]
        assert turn['turn_id'] == 2
        assert turn['sources'] == [{"source": "test"}]
    
    def test_conversation_context(self):
        """Test getting conversation context"""
        session = SessionData("test-session")
        
        # Add multiple turns
        for i in range(10):
            session.add_conversation_turn(f"Question {i}", f"Answer {i}", [])
        
        # Get last 5 turns
        context = session.get_conversation_context(max_turns=5)
        assert len(context) == 5
        assert context[0]['turn_id'] == 6  # Should be turns 6-10
        assert context[-1]['turn_id'] == 10
        
        # Get more turns than available
        context = session.get_conversation_context(max_turns=20)
        assert len(context) == 10  # Should return all 10 turns
    
    def test_session_expiry(self):
        """Test session expiry logic"""
        session = SessionData("test-session")
        
        # Fresh session should not be expired
        assert not session.is_expired(timeout_minutes=60)
        
        # Manually set old last_activity
        session.last_activity = datetime.now() - timedelta(minutes=90)
        assert session.is_expired(timeout_minutes=60)
        
        # Update activity should reset expiry
        session.update_activity()
        assert not session.is_expired(timeout_minutes=60)
    
    def test_session_serialization(self):
        """Test session to_dict method"""
        session = SessionData("test-session")
        session.add_conversation_turn("Test question", "Test answer", [])
        
        data = session.to_dict()
        
        assert data['session_id'] == "test-session"
        assert 'created_at' in data
        assert 'last_activity' in data
        assert data['conversation_turns'] == 1
        assert data['pinecone_thread_id'] is None
        assert data['tts_preferences']['enabled'] is True


class TestSessionManager:
    """Test SessionManager class"""
    
    def test_session_creation(self):
        """Test creating new sessions"""
        manager = SessionManager()
        
        session_id = manager.create_session()
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID4 length
        
        # Session should exist
        session = manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
    
    def test_get_nonexistent_session(self):
        """Test getting non-existent session"""
        manager = SessionManager()
        
        session = manager.get_session("nonexistent-session")
        assert session is None
    
    def test_get_or_create_session(self):
        """Test get_or_create_session method"""
        manager = SessionManager()
        
        # Create new session when none provided
        session_id1, session1 = manager.get_or_create_session()
        assert session1 is not None
        assert session1.session_id == session_id1
        
        # Get existing session
        session_id2, session2 = manager.get_or_create_session(session_id1)
        assert session_id2 == session_id1
        assert session2.session_id == session_id1
        
        # Create new session when invalid ID provided
        session_id3, session3 = manager.get_or_create_session("invalid-id")
        assert session_id3 != session_id1
        assert session3.session_id == session_id3
    
    def test_session_removal(self):
        """Test removing sessions"""
        manager = SessionManager()
        
        session_id = manager.create_session()
        assert manager.get_session(session_id) is not None
        
        # Remove session
        removed = manager.remove_session(session_id)
        assert removed is True
        assert manager.get_session(session_id) is None
        
        # Try to remove non-existent session
        removed = manager.remove_session("nonexistent")
        assert removed is False
    
    def test_expired_session_cleanup(self):
        """Test automatic cleanup of expired sessions"""
        manager = SessionManager(session_timeout_minutes=1)  # 1 minute timeout
        
        session_id = manager.create_session()
        session = manager.get_session(session_id)
        
        # Manually expire the session
        session.last_activity = datetime.now() - timedelta(minutes=2)
        
        # Getting expired session should remove it
        retrieved_session = manager.get_session(session_id)
        assert retrieved_session is None
    
    def test_session_stats(self):
        """Test session statistics"""
        manager = SessionManager()
        
        # Create some sessions with conversations
        for i in range(3):
            session_id = manager.create_session()
            session = manager.get_session(session_id)
            for j in range(i + 1):  # Different number of conversations per session
                session.add_conversation_turn(f"Q{j}", f"A{j}", [])
        
        stats = manager.get_session_stats()
        
        assert stats['active_sessions'] == 3
        assert stats['total_conversation_turns'] == 6  # 1 + 2 + 3
        assert stats['session_timeout_minutes'] == 60
        assert 'average_session_age_minutes' in stats
    
    def test_list_sessions(self):
        """Test listing all sessions"""
        manager = SessionManager()
        
        # Create some sessions
        session_ids = []
        for i in range(3):
            session_id = manager.create_session()
            session_ids.append(session_id)
        
        sessions_list = manager.list_sessions()
        
        assert len(sessions_list) == 3
        for session_data in sessions_list:
            assert session_data['session_id'] in session_ids
            assert 'created_at' in session_data
            assert 'conversation_turns' in session_data


class TestGlobalSessionManager:
    """Test global session manager functions"""
    
    def test_global_session_manager(self):
        """Test global session manager singleton"""
        manager1 = get_session_manager()
        manager2 = get_session_manager()
        
        # Should be the same instance
        assert manager1 is manager2
    
    def test_convenience_functions(self):
        """Test convenience functions"""
        from src.web.session_manager import create_session, get_session, get_or_create_session
        
        # Create session
        session_id = create_session()
        assert isinstance(session_id, str)
        
        # Get session
        session = get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
        
        # Get or create
        session_id2, session2 = get_or_create_session(session_id)
        assert session_id2 == session_id
        assert session2.session_id == session_id


if __name__ == "__main__":
    pytest.main([__file__])