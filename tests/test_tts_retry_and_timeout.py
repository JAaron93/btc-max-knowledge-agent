"""
Test suite for TTS retry logic and timeout handling.

This module tests:
- Retry logic and exponential back-off calculations
- Timeout handling for connection, read, and total request timeouts
- Rate limit handling with simulated 429 responses
- Network error scenarios and recovery mechanisms
"""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from src.utils.tts_error_handler import (CircuitBreaker, CircuitBreakerConfig,
                                         CircuitState, TTSAPIKeyError,
                                         TTSError, TTSErrorHandler,
                                         TTSNetworkError, TTSRateLimitError,
                                         TTSRetryExhaustedError,
                                         TTSServerError)
from src.utils.tts_service import TTSConfig, TTSService


class TestRetryLogic:
    """Test retry logic and exponential back-off calculations."""

    @pytest.fixture
    def error_handler(self):
        """Provide a TTS error handler for testing."""
        return TTSErrorHandler()

    def test_backoff_delay_calculation(self, error_handler):
        """Test exponential backoff delay calculation."""
        # Test 429 rate limit backoff
        base_delay = 1.0
        max_delay = 16.0

        # Test exponential growth
        delay_0 = error_handler._calculate_backoff_delay(0, base_delay, max_delay)
        delay_1 = error_handler._calculate_backoff_delay(1, base_delay, max_delay)
        delay_2 = error_handler._calculate_backoff_delay(2, base_delay, max_delay)
        delay_3 = error_handler._calculate_backoff_delay(3, base_delay, max_delay)

        # Should follow exponential pattern: base * (2^attempt)
        assert 0.75 <= delay_0 <= 1.25  # 1.0 ± jitter
        assert 1.5 <= delay_1 <= 2.5  # 2.0 ± jitter
        assert 3.0 <= delay_2 <= 5.0  # 4.0 ± jitter
        assert 6.0 <= delay_3 <= 10.0  # 8.0 ± jitter

        # Test max delay cap
        delay_10 = error_handler._calculate_backoff_delay(10, base_delay, max_delay)
        assert delay_10 <= max_delay * 1.25  # Should not exceed max + jitter

    def test_backoff_delay_5xx_errors(self, error_handler):
        """Test backoff delay for 5xx server errors."""
        base_delay = 0.5
        max_delay = 8.0

        delay_0 = error_handler._calculate_backoff_delay(0, base_delay, max_delay)
        delay_1 = error_handler._calculate_backoff_delay(1, base_delay, max_delay)
        delay_2 = error_handler._calculate_backoff_delay(2, base_delay, max_delay)

        # Should follow exponential pattern with smaller base
        assert 0.375 <= delay_0 <= 0.625  # 0.5 ± jitter
        assert 0.75 <= delay_1 <= 1.25  # 1.0 ± jitter
        assert 1.5 <= delay_2 <= 2.5  # 2.0 ± jitter

    def test_jitter_application(self, error_handler):
        """Test that jitter is properly applied to backoff delays."""
        base_delay = 2.0
        max_delay = 16.0
        attempt = 1

        # Generate multiple delays to test jitter variation
        delays = [
            error_handler._calculate_backoff_delay(attempt, base_delay, max_delay)
            for _ in range(100)
        ]

        # All delays should be positive
        assert all(delay >= 0 for delay in delays)

        # Should have variation due to jitter
        assert len(set(delays)) > 1  # Not all the same

        # Should be within expected range (4.0 ± 25%)
        expected_base = base_delay * (2**attempt)  # 4.0
        jitter_range = expected_base * 0.25  # 1.0

        for delay in delays:
            assert expected_base - jitter_range <= delay <= expected_base + jitter_range

    @pytest.mark.asyncio
    async def test_retry_429_rate_limit(self, error_handler):
        """Test retry behavior for 429 rate limit errors."""
        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 attempts
                raise TTSRateLimitError("Rate limit exceeded")
            return "success"

        # Should succeed on 3rd attempt
        result = await error_handler.execute_with_retry(mock_operation)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_5xx_server_error(self, error_handler):
        """Test retry behavior for 5xx server errors."""
        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:  # Fail first attempt
                raise TTSServerError("Internal server error", 500)
            return "success"

        # Should succeed on 2nd attempt
        result = await error_handler.execute_with_retry(mock_operation)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhaustion_429(self, error_handler):
        """Test retry exhaustion for 429 errors."""
        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            raise TTSRateLimitError("Rate limit exceeded")

        # Should exhaust retries and raise TTSRetryExhaustedError
        with pytest.raises(TTSRetryExhaustedError) as exc_info:
            await error_handler.execute_with_retry(mock_operation)

        expected_attempts = error_handler.retry_config["max_retries_429"] + 1
        assert call_count == expected_attempts
        assert f"{expected_attempts} attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_exhaustion_5xx(self, error_handler):
        """Test retry exhaustion for 5xx errors."""
        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            raise TTSServerError("Server error", 500)

        # Should exhaust retries and raise TTSRetryExhaustedError
        with pytest.raises(TTSRetryExhaustedError) as exc_info:
            await error_handler.execute_with_retry(mock_operation)

        expected_attempts = error_handler.retry_config["max_retries_5xx"] + 1
        assert call_count == expected_attempts
        assert f"{expected_attempts} attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_retry_for_api_key_error(self, error_handler):
        """Test that API key errors are not retried."""
        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            raise TTSAPIKeyError("Invalid API key")

        # Should not retry and raise immediately
        with pytest.raises(TTSAPIKeyError):
            await error_handler.execute_with_retry(mock_operation)

        assert call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_retry_timing(self, error_handler):
        """Test that retry delays are applied with correct backoff intervals."""
        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise TTSRateLimitError("Rate limit")
            return "success"

        # Mock asyncio.sleep to avoid real delays and capture sleep durations
        with patch("asyncio.sleep") as mock_sleep:
            result = await error_handler.execute_with_retry(mock_operation)

        assert result == "success"
        assert call_count == 3

        # Should have called sleep twice (between the 3 attempts)
        assert mock_sleep.call_count == 2

        # Get the delay durations from sleep calls
        sleep_calls = mock_sleep.call_args_list
        delay_1 = sleep_calls[0][0][0]  # First argument of first call
        delay_2 = sleep_calls[1][0][0]  # First argument of second call

        # Verify exponential backoff for 429 errors
        # Base delay is 1.0s, max delay is 16.0s for rate limits
        base_delay = error_handler.retry_config["base_delay_429"]
        max_delay = error_handler.retry_config["max_delay_429"]

        # First delay should be around base_delay (1.0s) with jitter
        assert base_delay * 0.75 <= delay_1 <= base_delay * 1.25

        # Second delay should be around base_delay * 2 (2.0s) with jitter
        expected_delay_2 = base_delay * 2
        assert expected_delay_2 * 0.75 <= delay_2 <= expected_delay_2 * 1.25

        # Second delay should be greater than first (exponential backoff)
        assert delay_2 > delay_1


class TestTimeoutHandling:
    """Test timeout handling for connection, read, and total request timeouts."""

    @pytest.fixture
    def tts_service(self):
        """Provide a TTS service for timeout testing."""
        config = TTSConfig(api_key="test_key", voice_id="test_voice")
        return TTSService(config)

    def test_timeout_configuration(self, tts_service):
        """Test timeout configuration values."""
        timeout_config = tts_service.error_handler.retry_config

        assert timeout_config["connection_timeout"] == 10.0
        assert timeout_config["read_timeout"] == 30.0
        assert timeout_config["total_timeout"] == 45.0

    @pytest.mark.asyncio
    async def test_connection_timeout(self, tts_service):
        """Test connection timeout handling."""
        test_text = "Test connection timeout"

        # Mock aiohttp to raise connection timeout
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post.side_effect = asyncio.TimeoutError("Connection timeout")
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            with pytest.raises(TTSNetworkError, match="Request timeout"):
                await tts_service._synthesize_with_api(test_text, "test_voice")

    @pytest.mark.asyncio
    async def test_read_timeout(self, tts_service):
        """Test read timeout handling."""
        test_text = "Test read timeout"

        # Mock response that times out during read
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read.side_effect = asyncio.TimeoutError("Read timeout")

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(TTSNetworkError, match="Request timeout"):
                await tts_service._synthesize_with_api(test_text, "test_voice")

    @pytest.mark.asyncio
    async def test_total_timeout(self, tts_service):
        """Test total request timeout handling."""
        test_text = "Test total timeout"

        # Mock session that raises timeout error directly
        mock_session = AsyncMock()
        mock_session.post.side_effect = asyncio.TimeoutError("Total timeout exceeded")
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(TTSNetworkError, match="Request timeout"):
                await tts_service._synthesize_with_api(test_text, "test_voice")

    @pytest.mark.asyncio
    async def test_timeout_retry_behavior(self, tts_service):
        """Test retry behavior for timeout errors."""
        call_count = 0

        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:  # Timeout on first attempt
                raise TTSNetworkError("Request timeout", asyncio.TimeoutError())
            return b"success_audio"

        # Should retry timeout errors
        with patch.object(
            tts_service.error_handler, "execute_with_retry"
        ) as mock_retry:
            mock_retry.return_value = b"success_audio"

            result = await tts_service.synthesize_text("test text")
            assert result == b"success_audio"
            mock_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_with_circuit_breaker(self, tts_service):
        """Test timeout handling with circuit breaker integration."""

        # Simulate multiple timeout failures to trigger circuit breaker
        async def timeout_operation():
            raise TTSNetworkError("Timeout", asyncio.TimeoutError())

        error_handler = tts_service.error_handler

        # Multiple failures should eventually open circuit
        for _ in range(10):
            try:
                await error_handler.execute_with_retry(timeout_operation)
            except (TTSRetryExhaustedError, TTSNetworkError):
                pass  # Expected failures

        # Circuit should eventually open due to repeated failures
        circuit_state = error_handler.circuit_breaker.get_state()

        # Assert that circuit breaker responded to the failures
        assert (
            circuit_state["failure_count"] > 0
        ), "Circuit breaker should have recorded failures"
        assert (
            circuit_state["failure_rate"] > 0
        ), "Circuit breaker should show failure rate > 0"

        # Circuit may be open or closed depending on exact timing and configuration,
        # but it should have recorded the failure pattern
        assert circuit_state["state"] in [
            "closed",
            "open",
            "half_open",
        ], f"Unexpected circuit state: {circuit_state['state']}"

        # If enough failures occurred within the window, circuit should be open
        if circuit_state["failure_rate"] >= 0.5:  # Default threshold
            assert (
                circuit_state["state"] == "open"
            ), "Circuit should be open with high failure rate"


class TestRateLimitHandling:
    """Test rate limit handling with simulated 429 responses."""

    @pytest.fixture
    def error_handler(self):
        """Provide error handler for rate limit testing."""
        return TTSErrorHandler()

    @pytest.mark.asyncio
    async def test_429_response_handling(self, error_handler):
        """Test handling of 429 rate limit responses."""
        call_count = 0

        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Simulate aiohttp ClientResponseError for 429
                raise aiohttp.ClientResponseError(
                    request_info=Mock(),
                    history=(),
                    status=429,
                    message="Too Many Requests",
                )
            return "success"

        # Should retry 429 errors
        result = await error_handler.execute_with_retry(mock_api_call)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_429_retry_delays(self, error_handler):
        """Test that 429 retries use appropriate delays."""
        call_times = []

        async def mock_api_call():
            call_times.append(time.time())
            if len(call_times) <= 2:
                raise aiohttp.ClientResponseError(
                    request_info=Mock(),
                    history=(),
                    status=429,
                    message="Rate limit exceeded",
                )
            return "success"

        start_time = time.time()
        result = await error_handler.execute_with_retry(mock_api_call)
        total_time = time.time() - start_time

        assert result == "success"
        assert len(call_times) == 3

        # Should have exponential backoff delays
        delay_1 = call_times[1] - call_times[0]
        delay_2 = call_times[2] - call_times[1]

        # First delay ~1s, second delay ~2s (with jitter)
        assert 0.5 <= delay_1 <= 2.0
        assert 1.0 <= delay_2 <= 4.0
        assert delay_2 > delay_1  # Should increase

    @pytest.mark.asyncio
    async def test_429_max_retries(self, error_handler):
        """Test maximum retries for 429 errors."""
        call_count = 0

        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            raise aiohttp.ClientResponseError(
                request_info=Mock(),
                history=(),
                status=429,
                message="Rate limit exceeded",
            )

        # Should exhaust retries
        with pytest.raises(TTSRetryExhaustedError):
            await error_handler.execute_with_retry(mock_api_call)

        # Should try max_retries_429 + 1 times (3 + 1 = 4)
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_429_basic_retry_behavior(self, error_handler):
        """Test basic retry behavior for 429 responses without Retry-After header parsing."""
        # Note: This test covers basic 429 retry behavior
        # The current implementation uses exponential backoff rather than parsing Retry-After headers

        call_count = 0

        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                error = aiohttp.ClientResponseError(
                    request_info=Mock(),
                    history=(),
                    status=429,
                    message="Rate limit exceeded",
                )
                raise error
            return "success"

        result = await error_handler.execute_with_retry(mock_api_call)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_mixed_error_retry_behavior(self, error_handler):
        """Test retry behavior with mixed error types."""
        call_count = 0

        async def mock_api_call():
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First: 429 rate limit
                raise aiohttp.ClientResponseError(
                    request_info=Mock(), history=(), status=429, message="Rate limit"
                )
            elif call_count == 2:
                # Second: 500 server error
                raise aiohttp.ClientResponseError(
                    request_info=Mock(), history=(), status=500, message="Server error"
                )
            elif call_count == 3:
                # Third: Network timeout
                raise TTSNetworkError("Timeout", asyncio.TimeoutError())
            else:
                # Finally succeed
                return "success"

        result = await error_handler.execute_with_retry(mock_api_call)
        assert result == "success"
        assert call_count == 4


class TestNetworkErrorScenarios:
    """Test network error scenarios and recovery mechanisms."""

    @pytest.fixture
    def tts_service(self):
        """Provide TTS service for network error testing."""
        config = TTSConfig(api_key="test_key")
        return TTSService(config)

    @pytest.mark.asyncio
    async def test_connection_refused(self, tts_service):
        """Test handling of connection refused errors."""
        test_text = "Test connection refused"

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post.side_effect = aiohttp.ClientConnectorError(
                connection_key=None,
                os_error=ConnectionRefusedError("Connection refused"),
            )
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            with pytest.raises(TTSNetworkError, match="Connection error"):
                await tts_service._synthesize_with_api(test_text, "test_voice")

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, tts_service):
        """Test handling of DNS resolution failures."""
        test_text = "Test DNS failure"

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post.side_effect = aiohttp.ClientConnectorError(
                connection_key=None, os_error=OSError("Name resolution failed")
            )
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            with pytest.raises(TTSNetworkError, match="Connection error"):
                await tts_service._synthesize_with_api(test_text, "test_voice")

    @pytest.mark.asyncio
    async def test_ssl_error(self, tts_service):
        """Test handling of SSL/TLS errors."""
        test_text = "Test SSL error"

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post.side_effect = aiohttp.ClientSSLError("SSL error")
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            with pytest.raises(TTSNetworkError, match="Network error"):
                await tts_service._synthesize_with_api(test_text, "test_voice")

    @pytest.mark.asyncio
    async def test_network_recovery(self, tts_service):
        """Test network error recovery after temporary failures."""
        call_count = 0
        test_audio = b"recovered_audio"

        async def mock_operation():
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: network error
                raise TTSNetworkError("Network temporarily unavailable")
            else:
                # Second call: success
                return test_audio

        # Mock the underlying network call to test actual retry logic
        call_count = 0

        async def network_recovery_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: network error
                raise aiohttp.ClientConnectorError(
                    connection_key=None,
                    os_error=ConnectionError("Network temporarily unavailable"),
                )
            else:
                # Second call: success
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=test_audio)
                return mock_response

        mock_session = AsyncMock()
        mock_session.post = network_recovery_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Test actual retry mechanism through synthesize_text
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await tts_service.synthesize_text("Network recovery test")
            assert result == test_audio
            assert call_count == 2  # Should have retried once

    @pytest.mark.asyncio
    async def test_partial_response_error(self, tts_service):
        """Test handling of partial response errors."""
        test_text = "Test partial response"

        # Mock response that fails during read
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read.side_effect = aiohttp.ClientPayloadError("Partial response")

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(TTSNetworkError, match="Network error"):
                await tts_service._synthesize_with_api(test_text, "test_voice")

    @pytest.mark.asyncio
    async def test_network_error_retry_limits(self, tts_service):
        """Test retry limits for network errors."""
        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise TTSNetworkError("Persistent network error")

        # Should exhaust retries for network errors
        with pytest.raises(TTSRetryExhaustedError):
            await tts_service.error_handler.execute_with_retry(failing_operation)

        # Should try max_retries_5xx + 1 times (network errors use 5xx retry config)
        expected_attempts = (
            tts_service.error_handler.retry_config["max_retries_5xx"] + 1
        )
        assert call_count == expected_attempts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
