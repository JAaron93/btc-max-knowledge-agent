#!/usr/bin/env python3
"""
Session Management for Bitcoin Knowledge Assistant
Provides conversation isolation without user authentication

Session ID Configuration:
- Default format: 32-character hexadecimal strings (e.g., 'a1b2c3d4e5f6789012345678901234ab')
- Configurable length and character set via SessionManager constructor
- Minimum length: 16 characters (for security)
- Minimum charset size: 2 characters
- Environment variables: SESSION_ID_LENGTH, SESSION_ID_CHARSET

Security Features:
- Cryptographically secure random generation using multiple entropy sources
- Collision detection with automatic regeneration
- Configurable format for different security requirements
- SHA-256 based entropy combination for consistent output
"""

import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import logging

logger = logging.getLogger(__name__)


class SessionData:
    """Represents a user session with conversation context"""
    
    def __init__(self, session_id: str, max_history_turns: int = 50):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.conversation_history: List[Dict[str, Any]] = []
        self._next_turn_id = 1
        self.max_history_turns = max_history_turns  # Limit conversation history size
        self.pinecone_thread_id: Optional[str] = None
        self.tts_preferences = {
            'enabled': True,
            'volume': 0.7
        }
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()

    def add_conversation_turn(self, question: str, answer: str, sources: List[Dict] = None):
        """Add a conversation turn to history with automatic memory management"""
        self.conversation_history.append({
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'sources': sources or [],
            'turn_id': self._next_turn_id
        })
        self._next_turn_id += 1
        
        # Automatically trim history to prevent memory bloat
        if len(self.conversation_history) > self.max_history_turns:
            # Keep only the most recent turns
            self.conversation_history = self.conversation_history[-self.max_history_turns:]
            logger.info(f"Trimmed conversation history for session {self.session_id[:8]}... to {self.max_history_turns} turns")
        
        self.update_activity()
    
    def get_conversation_context(self, max_turns: int = 5) -> List[Dict[str, Any]]:
        """Get recent conversation context for continuity"""
        return self.conversation_history[-max_turns:] if self.conversation_history else []
    
    def is_expired(self, timeout_minutes: int = 60) -> bool:
        """Check if session has expired"""
        expiry_time = self.last_activity + timedelta(minutes=timeout_minutes)
        return datetime.now() > expiry_time
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get approximate memory usage statistics for this session"""
        try:
            from pympler import asizeof
            history_size = asizeof.asizeof(self.conversation_history)
        except ImportError:
            # Fallback to a simple estimation based on string representation
            import json
            history_size = len(json.dumps(self.conversation_history, default=str).encode('utf-8'))

        return {
            'conversation_turns': len(self.conversation_history),
            'estimated_memory_bytes': history_size,
            'estimated_memory_kb': round(history_size / 1024, 2),
            'max_history_turns': self.max_history_turns,
            'memory_limit_reached': len(self.conversation_history) >= self.max_history_turns
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization"""
        # Note: conversation_history is deliberately excluded from serialization
        # for performance optimization (can be large) and privacy concerns.
        # Only the conversation count is included for monitoring purposes.
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'conversation_turns': len(self.conversation_history),
            'max_history_turns': self.max_history_turns,
            'pinecone_thread_id': self.pinecone_thread_id,
            'tts_preferences': self.tts_preferences
        }


class SessionManager:
    """
    Manages user sessions with automatic cleanup
    
    Session ID Format:
    - Default: 32-character hexadecimal strings (e.g., 'a1b2c3d4e5f6789012345678901234ab')
    - Generated using SHA-256 hash of combined entropy sources
    - Configurable length and character set via constructor parameters
    - Cryptographically secure with collision detection
    
    Entropy Sources:
    - UUID4 (128-bit random)
    - Microsecond timestamp
    - 16 bytes of cryptographically secure random data
    """
    
    def __init__(self, 
                 session_timeout_minutes: int = None, 
                 cleanup_interval_minutes: int = None, 
                 max_history_turns: int = None,
                 session_id_length: int = None,
                 session_id_charset: str = None):
        import os
        
        self.sessions: Dict[str, SessionData] = {}
        self.session_timeout_minutes = session_timeout_minutes or int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
        self.cleanup_interval_minutes = cleanup_interval_minutes or int(os.getenv("SESSION_CLEANUP_INTERVAL_MINUTES", "10"))
        self.max_history_turns = max_history_turns or int(os.getenv("SESSION_MAX_HISTORY_TURNS", "50"))
        
        # Session ID configuration
        self.session_id_length = session_id_length or int(os.getenv("SESSION_ID_LENGTH", "32"))
        self.session_id_charset = session_id_charset or os.getenv("SESSION_ID_CHARSET", "0123456789abcdef")
        
        # Validate session ID configuration
        if self.session_id_length < 16:
            raise ValueError("Session ID length must be at least 16 characters for security")
        if len(self.session_id_charset) < 2:
            raise ValueError("Session ID charset must contain at least 2 characters")
        
        self._lock = threading.RLock()
        self._cleanup_timer: Optional[threading.Timer] = None
        self._shutdown = False
        
        # Start background cleanup timer
        self._start_cleanup_timer()
        
        logger.info(f"SessionManager initialized with {self.session_timeout_minutes}min timeout, "
                   f"{self.max_history_turns} max turns per session, "
                   f"{self.session_id_length}-char session IDs using charset: {self.session_id_charset[:10]}...")
    
    def create_session(self) -> tuple[str, SessionData]:
        """
        Create a new session with cryptographically secure ID generation
        
        Returns:
            tuple[str, SessionData]: Session ID and session data object
            
        Session ID Generation:
        - Uses multiple entropy sources for maximum security
        - Format determined by session_id_length and session_id_charset parameters
        - Default: 32-character hexadecimal string
        - Includes collision detection and automatic regeneration
        """
        session_id = self._generate_session_id()
        
        with self._lock:
            # Ensure uniqueness (extremely unlikely collision, but safety first)
            collision_count = 0
            while session_id in self.sessions:
                collision_count += 1
                logger.warning(f"Session ID collision detected (attempt {collision_count}), regenerating...")
                session_id = self._generate_session_id()
                
                # Prevent infinite loop in case of implementation issues
                if collision_count > 10:
                    raise RuntimeError("Unable to generate unique session ID after 10 attempts")
            
            session_data = SessionData(session_id, self.max_history_turns)
            self.sessions[session_id] = session_data
            
            logger.info(f"Created new session: {session_id[:8]}... (length: {len(session_id)})")
            return session_id, session_data
    
    def _generate_session_id(self) -> str:
        """
        Generate a cryptographically secure session ID
        
        Returns:
            str: Session ID with configured length and character set
        """
        # Generate cryptographically secure session ID with multiple entropy sources
        base_uuid = str(uuid.uuid4())
        timestamp = str(int(datetime.now().timestamp() * 1_000_000))  # Microsecond precision timestamp
        random_bytes = secrets.token_hex(16)  # 16 bytes of cryptographically secure random data
        
        # Combine entropy sources and hash for consistent format
        combined_entropy = f"{base_uuid}-{timestamp}-{random_bytes}"
        full_hash = hashlib.sha256(combined_entropy.encode()).hexdigest()
        
        # Convert to desired character set if not hexadecimal
        if self.session_id_charset == "0123456789abcdef":
            # Optimized path for hexadecimal (default)
            session_id = full_hash[:self.session_id_length]
        else:
            # Convert hash to custom character set
            session_id = self._convert_to_charset(full_hash, self.session_id_charset, self.session_id_length)
        
        return session_id
    
    def _convert_to_charset(self, hex_string: str, charset: str, target_length: int) -> str:
        """
        Convert hexadecimal string to custom character set
        
        Args:
            hex_string: Input hexadecimal string
            charset: Target character set
            target_length: Desired output length
            
        Returns:
            str: String using only characters from charset
        """
        # Convert hex to integer
        num = int(hex_string, 16)
        
        # Convert to target base
        base = len(charset)
        result = []
        
        while num > 0 and len(result) < target_length:
            result.append(charset[num % base])
            num //= base
        
        # Pad with first character if needed
        while len(result) < target_length:
            result.append(charset[0])
        
        return ''.join(result[:target_length])
    
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
        
        # Create new session - returns both ID and SessionData directly
        return self.create_session()
    
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
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if session.is_expired(self.session_timeout_minutes):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self._remove_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def _start_cleanup_timer(self):
        """Start the background cleanup timer"""
        if self._shutdown:
            return
            
        # Schedule next cleanup
        self._cleanup_timer = threading.Timer(
            self.cleanup_interval_minutes * 60,
            self._background_cleanup
        )
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()
    
    def _background_cleanup(self):
        """Background cleanup method that runs in a separate thread"""
        try:
            with self._lock:
                if not self._shutdown:
                    self._cleanup_expired_sessions()
        except Exception as e:
            logger.error(f"Error during background cleanup: {e}")
        finally:
            # Schedule next cleanup if not shutting down
            if not self._shutdown:
                self._start_cleanup_timer()
    
    def shutdown(self):
        """Shutdown the session manager and stop background cleanup"""
        self._shutdown = True
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        logger.info("SessionManager shutdown completed")
    
    def cleanup_expired_sessions(self):
        """Public method to force cleanup of expired sessions"""
        with self._lock:
            self._cleanup_expired_sessions()
    
    def get_session_id_config(self) -> Dict[str, Any]:
        """
        Get session ID configuration information
        
        Returns:
            Dict containing session ID format specifications
        """
        return {
            'length': self.session_id_length,
            'charset': self.session_id_charset,
            'charset_size': len(self.session_id_charset),
            'format_description': f"{self.session_id_length}-character string using charset: {self.session_id_charset}",
            'example_pattern': f"{''.join([self.session_id_charset[0]] * min(8, self.session_id_length))}..." if self.session_id_length > 8 else ''.join([self.session_id_charset[0]] * self.session_id_length),
            'entropy_bits': self.session_id_length * (len(self.session_id_charset).bit_length() - 1)
        }
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about active sessions"""
        with self._lock:
            active_sessions = len(self.sessions)
            total_conversations = sum(len(s.conversation_history) for s in self.sessions.values())
            
            # Calculate session ages
            now = datetime.now()
            session_ages = []
            total_memory_kb = 0
            sessions_at_limit = 0
            
            for session in self.sessions.values():
                age_minutes = (now - session.created_at).total_seconds() / 60
                session_ages.append(age_minutes)
                
                # Memory usage
                memory_info = session.get_memory_usage()
                total_memory_kb += memory_info['estimated_memory_kb']
                if memory_info['memory_limit_reached']:
                    sessions_at_limit += 1
            
            avg_age = sum(session_ages) / len(session_ages) if session_ages else 0
            
            return {
                'active_sessions': active_sessions,
                'total_conversations': total_conversations,
                'average_session_age_minutes': avg_age,
                'total_memory_usage_kb': round(total_memory_kb, 2),
                'total_memory_usage_mb': round(total_memory_kb / 1024, 2),
                'sessions_at_memory_limit': sessions_at_limit,
                'max_history_turns_per_session': self.max_history_turns,
                'session_id_config': self.get_session_id_config()
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
    session_id, _ = get_session_manager().create_session()
    return session_id


def get_session(session_id: str) -> Optional[SessionData]:
    """Convenience function to get session data"""
    return get_session_manager().get_session(session_id)


def get_or_create_session(session_id: Optional[str] = None) -> tuple[str, SessionData]:
    """Convenience function to get or create session"""
    return get_session_manager().get_or_create_session(session_id)