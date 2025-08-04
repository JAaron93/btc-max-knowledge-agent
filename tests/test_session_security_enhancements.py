#!/usr/bin/env python3
"""
Tests for Enhanced Session Security Features
"""

import pytest
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.web.rate_limiter import RateLimiter, SessionRateLimiter
from src.web.session_manager import SessionManager


class TestRateLimiter:
    """Test rate limiting functionality"""
    
    def test_rate_limiter_allows_requests_under_limit(self):
        """Test that requests under the limit are allowed"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_id = "test_client"
        
        # First 5 requests should be allowed
        for i in range(5):
            assert limiter.is_allowed(client_id) == True
        
        # 6th request should be denied
        assert limiter.is_allowed(client_id) == False
    
    def test_rate_limiter_resets_after_window(self):
        """Test that rate limiter resets after time window"""
        limiter = RateLimiter(max_requests=2, window_seconds=1)  # 1 second window for testing
        client_id = "test_client"
        
        # Use up the limit
        assert limiter.is_allowed(client_id) == True
        assert limiter.is_allowed(client_id) == True
        assert limiter.is_allowed(client_id) == False
        
        # Wait for window to reset
        time.sleep(1.1)
        
        # Should be allowed again
        assert limiter.is_allowed(client_id) == True
    
    def test_rate_limiter_per_client_isolation(self):
        """Test that rate limiting is isolated per client"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        client1 = "client_1"
        client2 = "client_2"
        
        # Client 1 uses up their limit
        assert limiter.is_allowed(client1) == True
        assert limiter.is_allowed(client1) == True
        assert limiter.is_allowed(client1) == False
        
        # Client 2 should still be allowed
        assert limiter.is_allowed(client2) == True
        assert limiter.is_allowed(client2) == True
        assert limiter.is_allowed(client2) == False
    
    def test_rate_limiter_stats(self):
        """Test rate limiter statistics"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # Make some requests
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        limiter.is_allowed("client2")
        
        stats = limiter.get_stats()
        
        assert stats["active_clients"] == 2
        assert stats["total_active_requests"] == 3
        assert stats["max_requests_per_window"] == 5
        assert stats["window_seconds"] == 60


class TestSessionRateLimiter:
    """Test session-specific rate limiting"""
    
    def test_session_rate_limiter_different_limits(self):
        """Test that different endpoints have different limits"""
        limiter = SessionRateLimiter()
        client_ip = "192.168.1.100"
        
        # Session info has higher limit (20)
        for i in range(20):
            assert limiter.check_session_info_limit(client_ip) == True
        assert limiter.check_session_info_limit(client_ip) == False
        
        # Session delete has lower limit (5) - should still work for different endpoint
        for i in range(5):
            assert limiter.check_session_delete_limit(client_ip) == True
        assert limiter.check_session_delete_limit(client_ip) == False
    
    def test_session_rate_limiter_stats(self):
        """Test session rate limiter statistics"""
        limiter = SessionRateLimiter()
        
        # Make some requests
        limiter.check_session_info_limit("192.168.1.1")
        limiter.check_session_delete_limit("192.168.1.2")
        limiter.check_session_create_limit("192.168.1.3")
        
        stats = limiter.get_all_stats()
        
        assert "session_info" in stats
        assert "session_delete" in stats
        assert "session_create" in stats
        
        # Each should have 1 active client
        assert stats["session_info"]["active_clients"] == 1
        assert stats["session_delete"]["active_clients"] == 1
        assert stats["session_create"]["active_clients"] == 1


class TestEnhancedSessionManager:
    """Test enhanced session ID generation"""
    
    def test_cryptographically_secure_session_ids(self):
        """Test that session IDs are cryptographically secure with default configuration"""
        manager = SessionManager()
        
        # Get session ID configuration
        config = manager.get_session_id_config()
        expected_length = config['length']
        expected_charset = config['charset']
        
        # Generate multiple session IDs
        session_ids = set()
        for i in range(100):
            session_id, _ = manager.create_session()
            
            # Should match configured length
            assert len(session_id) == expected_length, f"Expected length {expected_length}, got {len(session_id)}"
            
            # Should be unique
            assert session_id not in session_ids, f"Duplicate session ID generated: {session_id}"
            session_ids.add(session_id)
            
            # Should use only characters from configured charset
            assert all(c in expected_charset for c in session_id), f"Session ID contains invalid characters: {session_id}"
    
    def test_configurable_session_id_format(self):
        """Test that session ID format can be configured"""
        # Test custom configuration
        custom_length = 16
        custom_charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        
        manager = SessionManager(
            session_id_length=custom_length,
            session_id_charset=custom_charset
        )
        
        # Verify configuration
        config = manager.get_session_id_config()
        assert config['length'] == custom_length
        assert config['charset'] == custom_charset
        
        # Test session ID generation with custom format
        session_ids = set()
        for i in range(50):
            session_id, _ = manager.create_session()
            
            # Should match custom length
            assert len(session_id) == custom_length
            
            # Should use only custom charset characters
            assert all(c in custom_charset for c in session_id)
            
            # Should be unique
            assert session_id not in session_ids
            session_ids.add(session_id)
    
    def test_session_id_configuration_validation(self):
        """Test that invalid session ID configurations are rejected"""
        # Test minimum length validation
        with pytest.raises(ValueError, match="Session ID length must be at least 16"):
            SessionManager(session_id_length=8)
        
        # Test charset validation
        with pytest.raises(ValueError, match="Session ID charset must contain at least 2"):
            SessionManager(session_id_charset="A")
    
    def test_session_id_collision_handling(self):
        """Test that session ID collisions are handled (though extremely unlikely)"""
        manager = SessionManager()
        config = manager.get_session_id_config()
        expected_length = config['length']
        charset = config['charset']
        
        # Mock the sessions dict to simulate a collision
        fake_session_id = charset[0] * expected_length
        manager.sessions[fake_session_id] = Mock()
        
        # Create a new session - should not collide
        with patch('hashlib.sha256') as mock_hash:
            # First call returns collision, second call returns unique ID
            collision_hash = fake_session_id + "0" * (64 - expected_length)  # Pad to 64 chars
            unique_hash = charset[1] * expected_length + "0" * (64 - expected_length)  # Pad to 64 chars
            
            mock_hash.return_value.hexdigest.side_effect = [
                collision_hash,  # Collision
                unique_hash  # Unique
            ]
            
            session_id, _ = manager.create_session()
            
            # Should get the non-colliding ID
            expected_unique_id = charset[1] * expected_length
            assert session_id == expected_unique_id
            assert session_id != fake_session_id
    
    def test_session_id_entropy_sources(self):
        """Test that session IDs use multiple entropy sources"""
        manager = SessionManager()
        config = manager.get_session_id_config()
        expected_length = config['length']
        
        # Generate session IDs at different times
        with patch('time.time', side_effect=[1000.0, 1000.1]):
            session_id1, _ = manager.create_session()
            session_id2, _ = manager.create_session()
        
        # Should be different due to timestamp entropy
        assert session_id1 != session_id2
        
        # Both should be valid format
        assert len(session_id1) == expected_length
        assert len(session_id2) == expected_length


class TestSecurityLogging:
    """Test security-related logging"""
    
    def test_session_access_logging(self):
        """Test that session lifecycle events are properly logged for security monitoring"""
        with patch('src.web.session_manager.logger') as mock_logger:
            manager = SessionManager()
            
            # Test session creation logging
            session_id, session_data = manager.create_session()
            
            # Verify session creation was logged
            mock_logger.info.assert_called()
            create_log_calls = [call for call in mock_logger.info.call_args_list 
                              if 'Created new session' in str(call)]
            assert len(create_log_calls) > 0, "Session creation should be logged"
            
            # Verify log contains session ID (truncated for security)
            create_log_message = str(create_log_calls[-1])
            assert session_id[:8] in create_log_message, "Log should contain truncated session ID"
            
            # Reset mock for next test
            mock_logger.reset_mock()
            
            # Test session expiry logging
            # Make session appear expired
            session_data.last_activity = datetime.now() - timedelta(hours=2)
            
            # Try to get expired session
            result = manager.get_session(session_id)
            assert result is None, "Expired session should return None"
            
            # Verify expiry was logged
            mock_logger.info.assert_called()
            expiry_log_calls = [call for call in mock_logger.info.call_args_list 
                               if 'expired and removed' in str(call)]
            assert len(expiry_log_calls) > 0, "Session expiry should be logged"
            
            # Reset mock for cleanup test
            mock_logger.reset_mock()
            
            # Test manual session removal logging
            new_session_id, _ = manager.create_session()
            mock_logger.reset_mock()  # Clear creation log
            
            removed = manager.remove_session(new_session_id)
            assert removed is True, "Session should be successfully removed"
            
            # Verify manual removal was logged
            mock_logger.info.assert_called()
            removal_log_calls = [call for call in mock_logger.info.call_args_list 
                                if 'Manually removed session' in str(call)]
            assert len(removal_log_calls) > 0, "Manual session removal should be logged"
    
    def test_rate_limit_violation_logging(self):
        """Test that rate limit violations are logged"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        client_id = "test_client"
        
        # First request allowed
        assert limiter.is_allowed(client_id) == True
        
        # Second request should be denied and logged
        with patch('src.web.rate_limiter.logger') as mock_logger:
            assert limiter.is_allowed(client_id) == False
            mock_logger.warning.assert_called_once()
            
            # Verify log message contains relevant information
            log_call = mock_logger.warning.call_args[0][0]
            assert "Rate limit exceeded" in log_call
            assert client_id in log_call


if __name__ == "__main__":
    pytest.main([__file__])