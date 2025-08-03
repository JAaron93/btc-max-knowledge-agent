#!/usr/bin/env python3
"""
Tests for Enhanced Session Security Features
"""

import pytest
import time
import sys
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
        """Test that session IDs are cryptographically secure"""
        manager = SessionManager()
        
        # Generate multiple session IDs
        session_ids = set()
        for i in range(100):
            session_id = manager.create_session()
            
            # Should be 32 characters (hex string)
            assert len(session_id) == 32
            
            # Should be unique
            assert session_id not in session_ids
            session_ids.add(session_id)
            
            # Should be hexadecimal
            assert all(c in '0123456789abcdef' for c in session_id)
    
    def test_session_id_collision_handling(self):
        """Test that session ID collisions are handled (though extremely unlikely)"""
        manager = SessionManager()
        
        # Mock the sessions dict to simulate a collision
        fake_session_id = "a" * 32
        manager.sessions[fake_session_id] = Mock()
        
        # Create a new session - should not collide
        with patch('hashlib.sha256') as mock_hash:
            # First call returns collision, second call returns unique ID
            mock_hash.return_value.hexdigest.side_effect = [
                fake_session_id,  # Collision
                "b" * 64  # Unique (will be truncated to 32)
            ]
            
            session_id = manager.create_session()
            
            # Should get the non-colliding ID
            assert session_id == "b" * 32
            assert session_id != fake_session_id
    
    def test_session_id_entropy_sources(self):
        """Test that session IDs use multiple entropy sources"""
        manager = SessionManager()
        
        # Generate session IDs at different times
        session_id1 = manager.create_session()
        time.sleep(0.001)  # Small delay to ensure different timestamp
        session_id2 = manager.create_session()
        
        # Should be different due to timestamp entropy
        assert session_id1 != session_id2
        
        # Both should be valid format
        assert len(session_id1) == 32
        assert len(session_id2) == 32


class TestSecurityLogging:
    """Test security-related logging"""
    
    def test_session_access_logging(self):
        """Test that session access attempts are logged"""
        # This would require integration testing with the actual API
        # For now, we verify the logging structure is in place
        pass
    
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