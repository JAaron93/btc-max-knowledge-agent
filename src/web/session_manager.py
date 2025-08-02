#!/usr/bin/env python3
"""
Session Management for Bitcoin Knowledge Assistant
Provides conversation isolation without user authentication
"""

import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import logging

logger = logging.getLogger(__name__)


class SessionData:
    """Represents a user session with conversation context"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.conversation_history: List[Dict[str, Any]] = []
        self.pinecone_thread_id: Optional[str] = None
        self.tts_preferences = {
            'enabled': True,
            'volume': 0.7
        }
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
    
    def add_conversation_turn(self, question: str, answer: str, sources: List[Dict] = None):
        """Add a conversation turn to history"""
        self.conversation_history.append({
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'sources': sources or [],
            'turn_id': len(self.conversation_history) + 1
        })
        self.update_activity()
    
    def get_conversation_context(self, max_turns: int = 5) -> List[Dict[str, Any]]:
        """Get recent conversation context for continuity"""
        return self.conversation_history[-max_turns:] if self.conversation_history else []
    
    def is_expired(self, timeout_minutes: int = 60) -> bool:
        """Check if session has expired"""
        expiry_time = self.last_activity + timedelta(minutes=timeout_minutes)
        return datetime.now() > expiry_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'conversation_turns': len(self.conversation_history),
            'pinecone_thread_id': self.pinecone_thread_id,
            'tts_preferences': self.tts_preferences
        }


class SessionManager:
    """Manages user sessions with automatic cleanup"""
    
    def __init__(self, session_timeout_minutes: int = 60, cleanup_interval_minutes: int = 10):
        self.sessions: Dict[str, SessionData] = {}
        self.session_timeout_minutes = session_timeout_minutes
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        
        logger.info(f"SessionManager initialized with {session_timeout_minutes}min timeout")
    
    def create_session(self) -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        
        with self._lock:
            session_data = SessionData(session_id)
            self.sessions[session_id] = session_data
            
            # Periodic cleanup
            self._cleanup_expired_sessions()
            
            logger.info(f"Created new session: {session_id}")
            return session_id
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data by ID"""
        if not session_id:
            return None
            
        with self._lock:
            session = self.sessions.get(session_id)
            
            if session and session.is_expired(self.session_timeout_minutes):
                # Session expired, remove it
                self._remove_session(session_id)
                logger.info(f"Session expired and removed: {session_id}")
                return None
            
            if session:
                session.update_activity()
                
            return session
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> tuple[str, SessionData]:
        """Get existing session or create new one"""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session_id, session
        
        # Create new session
        new_session_id = self.create_session()
        session = self.get_session(new_session_id)
        return new_session_id, session
    
    def _remove_session(self, session_id: str):
        """Remove session (internal method, assumes lock is held)"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a specific session"""
        with self._lock:
            if session_id in self.sessions:
                self._remove_session(session_id)
                logger.info(f"Manually removed session: {session_id}")
                return True
            return False
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions (internal method, assumes lock is held)"""
        current_time = time.time()
        
        # Only run cleanup periodically
        if current_time - self._last_cleanup < (self.cleanup_interval_minutes * 60):
            return
        
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if session.is_expired(self.session_timeout_minutes):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self._remove_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        self._last_cleanup = current_time
    
    def cleanup_expired_sessions(self):
        """Public method to force cleanup of expired sessions"""
        with self._lock:
            self._cleanup_expired_sessions()
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about active sessions"""
        with self._lock:
            active_sessions = len(self.sessions)
            total_conversations = sum(len(s.conversation_history) for s in self.sessions.values())
            
            # Calculate session ages
            now = datetime.now()
            session_ages = []
            for session in self.sessions.values():
                age_minutes = (now - session.created_at).total_seconds() / 60
                session_ages.append(age_minutes)
            
            avg_age = sum(session_ages) / len(session_ages) if session_ages else 0
            
            return {
                'active_sessions': active_sessions,
                'total_conversation_turns': total_conversations,
                'average_session_age_minutes': round(avg_age, 2),
                'session_timeout_minutes': self.session_timeout_minutes,
                'cleanup_interval_minutes': self.cleanup_interval_minutes
            }
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions (for debugging/monitoring)"""
        with self._lock:
            return [session.to_dict() for session in self.sessions.values()]


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def create_session() -> str:
    """Convenience function to create a new session"""
    return get_session_manager().create_session()


def get_session(session_id: str) -> Optional[SessionData]:
    """Convenience function to get session data"""
    return get_session_manager().get_session(session_id)


def get_or_create_session(session_id: Optional[str] = None) -> tuple[str, SessionData]:
    """Convenience function to get or create session"""
    return get_session_manager().get_or_create_session(session_id)