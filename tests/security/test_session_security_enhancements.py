#!/usr/bin/env python3
"""
Tests for Enhanced Session Security Features
"""

import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.web.rate_limiter import RateLimiter, SessionRateLimiter
from src.web.session_manager import SessionManager

# Path setup is handled by conftest.py fixture automatically


class TestRateLimiter:
    """Test rate limiting functionality"""

    def test_rate_limiter_allows_requests_under_limit(self):
        """Test that requests under the limit are allowed"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_id = "test_client"

        # First 5 requests should be allowed
        for i in range(5):
            assert limiter.is_allowed(client_id)

        # 6th request should be denied
        assert not limiter.is_allowed(client_id)

    def test_rate_limiter_resets_after_window(self):
        """Test that rate limiter resets after time window"""
        limiter = RateLimiter(
            max_requests=2, window_seconds=1
        )  # 1 second window for testing
        client_id = "test_client"

        # Use up the limit
        assert limiter.is_allowed(client_id)
        assert limiter.is_allowed(client_id)
        assert not limiter.is_allowed(client_id)

        # Wait for window to reset
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.is_allowed(client_id)

    def test_rate_limiter_per_client_isolation(self):
        """Test that rate limiting is isolated per client"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        client1 = "client_1"
        client2 = "client_2"

        # Client 1 uses up their limit
        assert limiter.is_allowed(client1)
        assert limiter.is_allowed(client1)
        assert not limiter.is_allowed(client1)

        # Client 2 should still be allowed
        assert limiter.is_allowed(client2)
        assert limiter.is_allowed(client2)
        assert not limiter.is_allowed(client2)

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
            assert limiter.check_session_info_limit(client_ip)
        assert not limiter.check_session_info_limit(client_ip)

        # Session delete has lower limit (5) - should still work for different endpoint
        for i in range(5):
            assert limiter.check_session_delete_limit(client_ip)
        assert not limiter.check_session_delete_limit(client_ip)

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
        expected_length = config["length"]
        expected_charset = config["charset"]

        # Test 1: Verify cryptographically secure random sources are used
        with (
            patch("uuid.uuid4") as mock_uuid4,
            patch("secrets.token_hex") as mock_token_hex,
        ):
            # Configure mocks to return predictable values
            mock_uuid4.return_value = type(
                "MockUUID", (), {"__str__": lambda self: "test-uuid-4"}
            )()
            mock_token_hex.return_value = "secure_random_hex"

            # Generate a session ID
            session_id, _ = manager.create_session()

            # Verify cryptographically secure sources were called
            (
                mock_uuid4.assert_called_once(),
                "uuid.uuid4() should be called for secure randomness",
            )
            (
                mock_token_hex.assert_called_once_with(16),
                "secrets.token_hex(16) should be called for secure randomness",
            )

            # Verify session ID was generated (not None/empty)
            assert session_id is not None
            assert len(session_id) == expected_length

        # Test 2: Verify session ID properties without mocking
        session_ids = set()
        for i in range(100):
            session_id, _ = manager.create_session()

            # Should match configured length
            assert (
                len(session_id) == expected_length
            ), f"Expected length {expected_length}, got {len(session_id)}"

            # Should be unique
            assert (
                session_id not in session_ids
            ), f"Duplicate session ID generated: {session_id}"
            session_ids.add(session_id)

            # Should use only characters from configured charset
            assert all(
                c in expected_charset for c in session_id
            ), f"Session ID contains invalid characters: {session_id}"

        # Test 3: Verify cryptographic quality through statistical analysis
        # Generate many session IDs and verify they don't show patterns
        large_sample = set()
        for _ in range(1000):
            session_id, _ = manager.create_session()
            large_sample.add(session_id)

        # All should be unique (extremely high probability with secure randomness)
        assert (
            len(large_sample) == 1000
        ), "All session IDs should be unique with secure randomness"

        # Test character distribution (should be roughly uniform for secure randomness)
        char_counts = {}
        for session_id in large_sample:
            for char in session_id:
                char_counts[char] = char_counts.get(char, 0) + 1

        # With secure randomness, we should see most characters from the charset
        # (This is a statistical test - with 1000 32-char IDs, we have 32000 characters)
        unique_chars_used = len(char_counts)
        charset_size = len(expected_charset)

        # We should see at least 80% of the charset characters with good randomness
        min_expected_chars = int(charset_size * 0.8)
        assert unique_chars_used >= min_expected_chars, (
            f"Poor character distribution suggests weak randomness. "
            f"Used {unique_chars_used}/{charset_size} charset characters, expected >= {min_expected_chars}"
        )

    def test_configurable_session_id_format(self):
        """Test that session ID format can be configured"""
        # Test custom configuration
        custom_length = 16
        custom_charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

        manager = SessionManager(
            session_id_length=custom_length, session_id_charset=custom_charset
        )

        # Verify configuration
        config = manager.get_session_id_config()
        assert config["length"] == custom_length
        assert config["charset"] == custom_charset

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
        with pytest.raises(
            ValueError, match="Session ID charset must contain at least 2 characters"
        ):
            SessionManager(session_id_charset="A")

    def test_session_id_collision_handling(self):
        """Test that session ID collisions are handled (though extremely unlikely)"""
        manager = SessionManager()
        config = manager.get_session_id_config()
        expected_length = config["length"]
        charset = config["charset"]

        # Create predictable session IDs for collision testing
        collision_id = charset[0] * expected_length
        unique_id = charset[1] * expected_length

        # Mock the session ID generation method at a higher level
        with patch.object(manager, "_generate_session_id") as mock_generate:
            # First call returns collision, second call returns unique ID
            mock_generate.side_effect = [collision_id, unique_id]

            # Pre-populate sessions with the collision ID to simulate collision
            manager.sessions[collision_id] = Mock()

            # Create a new session - should detect collision and regenerate
            session_id, session_data = manager.create_session()

            # Should get the non-colliding ID
            assert session_id == unique_id
            assert session_id != collision_id
            assert session_id not in [collision_id]

            # Verify _generate_session_id was called twice (collision + retry)
            assert mock_generate.call_count == 2

            # Verify the session was actually created with the unique ID
            assert session_id in manager.sessions
            assert manager.sessions[session_id] == session_data

    def test_session_id_entropy_sources(self):
        """Test that session IDs use multiple entropy sources (UUID4, timestamp, random bytes)"""
        manager = SessionManager()
        config = manager.get_session_id_config()
        expected_length = config["length"]

        # Test 1: Timestamp entropy - Generate session IDs at different times
        with patch("time.time", side_effect=[1000.0, 1000.1]):
            session_id1, _ = manager.create_session()
            session_id2, _ = manager.create_session()

        # Should be different due to timestamp entropy
        assert session_id1 != session_id2
        assert len(session_id1) == expected_length
        assert len(session_id2) == expected_length

        # Test 2: UUID4 entropy - Mock UUID4 to return different values
        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.side_effect = [
                type("MockUUID", (), {"__str__": lambda self: "uuid-1-test"})(),
                type("MockUUID", (), {"__str__": lambda self: "uuid-2-test"})(),
            ]
            session_id3, _ = manager.create_session()
            session_id4, _ = manager.create_session()

        # Should be different due to UUID4 entropy
        assert session_id3 != session_id4
        assert len(session_id3) == expected_length
        assert len(session_id4) == expected_length

        # Test 3: Random bytes entropy - Mock secrets.token_hex to return different values
        with patch("secrets.token_hex") as mock_token_hex:
            mock_token_hex.side_effect = ["random1", "random2"]
            session_id5, _ = manager.create_session()
            session_id6, _ = manager.create_session()

        # Should be different due to random bytes entropy
        assert session_id5 != session_id6
        assert len(session_id5) == expected_length
        assert len(session_id6) == expected_length

        # Test 4: All entropy sources combined - Generate multiple IDs without mocking
        session_ids = []
        for _ in range(10):
            session_id, _ = manager.create_session()
            session_ids.append(session_id)

        # All should be unique (extremely high probability with multiple entropy sources)
        assert len(set(session_ids)) == len(
            session_ids
        ), "All session IDs should be unique"

        # All should have correct format
        for session_id in session_ids:
            assert len(session_id) == expected_length
            assert all(c in config["charset"] for c in session_id)


class TestSecurityLogging:
    """Test security-related logging"""

    def test_session_access_logging(self):
        """Test that session lifecycle events are properly logged for security monitoring"""
        with patch("src.web.session_manager.logger") as mock_logger:
            manager = SessionManager()

            # Test session creation logging
            session_id, session_data = manager.create_session()

            # Verify session creation was logged
            mock_logger.info.assert_called()
            create_log_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "Created new session" in str(call)
            ]
            assert len(create_log_calls) > 0, "Session creation should be logged"

            # Verify log contains session ID (truncated for security)
            create_log_message = str(create_log_calls[-1])
            assert (
                session_id[:8] in create_log_message
            ), "Log should contain truncated session ID"

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
            expiry_log_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "expired and removed" in str(call)
            ]
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
            removal_log_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "Manually removed session" in str(call)
            ]
            assert len(removal_log_calls) > 0, "Manual session removal should be logged"

    def test_rate_limit_violation_logging(self):
        """Test that rate limit violations are logged"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        client_id = "test_client"

        # First request allowed
        assert limiter.is_allowed(client_id)

        # Second request should be denied and logged
        with patch("src.web.rate_limiter.logger") as mock_logger:
            assert not limiter.is_allowed(client_id)
            mock_logger.warning.assert_called_once()

            # Verify log message contains relevant information
            log_call = mock_logger.warning.call_args[0][0]
            assert "Rate limit exceeded" in log_call
            assert client_id in log_call


if __name__ == "__main__":
    pytest.main([__file__])
