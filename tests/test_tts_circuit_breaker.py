"""
Test suite for TTS circuit breaker functionality.

This module tests:
- Circuit breaker state transitions (closed → open → half-open → closed)
- Circuit breaker behavior under various failure patterns and recovery scenarios
- Integration with TTS service and error handling
- Circuit breaker configuration and thresholds
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

from src.utils.tts_error_handler import (
    CircuitBreaker, CircuitState, CircuitBreakerConfig, TTSErrorHandler,
    TTSError, TTSRateLimitError, TTSServerError, TTSNetworkError, TTSCircuitOpenError
)
from src.utils.tts_service import TTSService, TTSConfig


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""
    
    def test_default_config(self):
        """Test default circuit breaker configuration."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 0.5  # 50%
        assert config.window_size == 10
        assert config.cooldown_period == 60  # seconds
        assert config.success_threshold == 3
    
    def test_custom_config(self):
        """Test custom circuit breaker configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=0.3,
            window_size=20,
            cooldown_period=120,
            success_threshold=5
        )
        
        assert config.failure_threshold == 0.3
        assert config.window_size == 20
        assert config.cooldown_period == 120
        assert config.success_threshold == 5


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Provide a circuit breaker with test configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=0.5,
            window_size=4,  # Small window for easier testing
            cooldown_period=1,  # Short cooldown for testing
            success_threshold=2
        )
        return CircuitBreaker(config)
    
    def test_initial_state(self, circuit_breaker):
        """Test initial circuit breaker state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
    
    def test_closed_to_open_transition(self, circuit_breaker):
        """Test transition from CLOSED to OPEN state."""
        # Record failures to reach threshold
        # With window_size=4 and failure_threshold=0.5, need 2+ failures
        circuit_breaker.record_failure()  # 1/1 = 100%
        assert circuit_breaker.state == CircuitState.CLOSED  # Not enough samples
        
        circuit_breaker.record_failure()  # 2/2 = 100%
        assert circuit_breaker.state == CircuitState.CLOSED  # Still not enough
        
        circuit_breaker.record_failure()  # 3/3 = 100%
        assert circuit_breaker.state == CircuitState.CLOSED  # Still not enough
        
        circuit_breaker.record_failure()  # 4/4 = 100% (window full)
        assert circuit_breaker.state == CircuitState.OPEN  # Should open now
        assert circuit_breaker.can_execute() is False
    
    def test_open_to_half_open_transition(self, circuit_breaker):
        """Test transition from OPEN to HALF_OPEN state."""
        # Force circuit to OPEN state
        for _ in range(4):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.can_execute() is False
        
        # Mock time progression to simulate cooldown period passing
        initial_time = datetime.now(timezone.utc)
        future_time = initial_time + timedelta(seconds=1.1)  # Slightly longer than cooldown_period
        
        with patch('src.utils.tts_error_handler.datetime') as mock_datetime:
            mock_datetime.now.return_value = future_time
            mock_datetime.timezone = timezone
            
            # Should transition to HALF_OPEN when checking can_execute
            assert circuit_breaker.can_execute() is True
            assert circuit_breaker.state == CircuitState.HALF_OPEN
    
    def test_half_open_to_closed_transition(self, circuit_breaker):
        """Test transition from HALF_OPEN to CLOSED state."""
        # Force circuit to HALF_OPEN state
        for _ in range(4):
            circuit_breaker.record_failure()
        
        # Mock time progression to simulate cooldown period passing
        initial_time = datetime.now(timezone.utc)
        future_time = initial_time + timedelta(seconds=1.1)
        
        with patch('src.utils.tts_error_handler.datetime') as mock_datetime:
            mock_datetime.now.return_value = future_time
            mock_datetime.timezone = timezone
            
            circuit_breaker.can_execute()  # Trigger transition to HALF_OPEN
        
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Record enough successes to close circuit
        circuit_breaker.record_success()  # 1 success
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        circuit_breaker.record_success()  # 2 successes (threshold reached)
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.can_execute() is True
    
    def test_half_open_to_open_transition(self, circuit_breaker):
        """Test transition from HALF_OPEN back to OPEN state."""
        # Force circuit to HALF_OPEN state
        for _ in range(4):
            circuit_breaker.record_failure()
        
        # Mock time progression to simulate cooldown period passing
        initial_time = datetime.now(timezone.utc)
        future_time = initial_time + timedelta(seconds=1.1)
        
        with patch('src.utils.tts_error_handler.datetime') as mock_datetime:
            mock_datetime.now.return_value = future_time
            mock_datetime.timezone = timezone
            
            circuit_breaker.can_execute()  # Trigger transition to HALF_OPEN
        
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Record failure during half-open state
        circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.can_execute() is False
    
    def test_failure_rate_calculation(self, circuit_breaker):
        """Test failure rate calculation in sliding window."""
        # Test empty window
        assert circuit_breaker._calculate_failure_rate() == 0.0
        
        # Test mixed successes and failures
        circuit_breaker.record_success()  # 0/1 = 0%
        assert circuit_breaker._calculate_failure_rate() == 0.0
        
        circuit_breaker.record_failure()  # 1/2 = 50%
        assert circuit_breaker._calculate_failure_rate() == 0.5
        
        circuit_breaker.record_failure()  # 2/3 = 66.7%
        assert abs(circuit_breaker._calculate_failure_rate() - 2/3) < 0.01
        
        circuit_breaker.record_success()  # 2/4 = 50%
        assert circuit_breaker._calculate_failure_rate() == 0.5
    
    def test_sliding_window_behavior(self, circuit_breaker):
        """Test sliding window behavior with window overflow."""
        # Fill window with successes
        for _ in range(4):
            circuit_breaker.record_success()
        
        assert len(circuit_breaker.request_window) == 4
        assert circuit_breaker._calculate_failure_rate() == 0.0
        
        # Add one more success (should evict oldest)
        circuit_breaker.record_success()
        assert len(circuit_breaker.request_window) == 4  # Still max size
        assert circuit_breaker._calculate_failure_rate() == 0.0
        
        # Add failures to test eviction
        circuit_breaker.record_failure()  # 1/4 = 25%
        circuit_breaker.record_failure()  # 2/4 = 50%
        
        assert circuit_breaker._calculate_failure_rate() == 0.5
        assert circuit_breaker.state == CircuitState.OPEN  # Should open at 50%
    
    def test_reset_functionality(self, circuit_breaker):
        """Test circuit breaker reset functionality."""
        # Force circuit to OPEN state
        for _ in range(4):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count > 0
        assert len(circuit_breaker.request_window) > 0
        
        # Reset circuit breaker
        circuit_breaker.reset()
        
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert len(circuit_breaker.request_window) == 0
        assert circuit_breaker.can_execute() is True
    
    def test_state_information(self, circuit_breaker):
        """Test circuit breaker state information reporting."""
        # Initial state
        state_info = circuit_breaker.get_state()
        
        assert state_info['state'] == 'closed'
        assert state_info['failure_rate'] == 0.0
        assert state_info['failure_count'] == 0
        assert state_info['success_count'] == 0
        assert state_info['window_size'] == 0
        assert state_info['can_execute'] is True
        assert state_info['last_failure_time'] is None
        assert state_info['opened_at'] is None
        
        # After some failures
        circuit_breaker.record_failure()
        circuit_breaker.record_success()
        
        state_info = circuit_breaker.get_state()
        assert state_info['failure_rate'] == 0.5
        assert state_info['failure_count'] == 1
        assert state_info['window_size'] == 2
        assert state_info['last_failure_time'] is not None


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with TTS error handler."""
    
    @pytest.fixture
    def error_handler(self):
        """Provide error handler with circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=0.5,
            window_size=4,
            cooldown_period=1,
            success_threshold=2
        )
        return TTSErrorHandler(config)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_execution(self, error_handler):
        """Test that open circuit breaker prevents execution."""
        # Force circuit breaker to open
        for _ in range(4):
            error_handler.circuit_breaker.record_failure()
        
        assert error_handler.circuit_breaker.state == CircuitState.OPEN
        
        # Should raise TTSCircuitOpenError immediately
        async def dummy_operation():
            return "should not execute"
        
        with pytest.raises(TTSCircuitOpenError):
            await error_handler.execute_with_retry(dummy_operation)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success_recording(self, error_handler):
        """Test that successful operations are recorded in circuit breaker."""
        call_count = 0
        
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await error_handler.execute_with_retry(successful_operation)
        
        assert result == "success"
        assert call_count == 1
        
        # Check that success was recorded
        state = error_handler.circuit_breaker.get_state()
        assert state['window_size'] == 1
        assert state['failure_rate'] == 0.0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_recording(self, error_handler):
        """Test that failed operations are recorded in circuit breaker."""
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise TTSServerError("Server error", 500)
        
        # Should exhaust retries and record failures
        with pytest.raises((TTSRetryExhaustedError, TTSServerError)):
            await error_handler.execute_with_retry(failing_operation)
        
        # Check that failures were recorded
        state = error_handler.circuit_breaker.get_state()
        assert state['failure_count'] > 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_cycle(self, error_handler):
        """Test complete circuit breaker recovery cycle."""
        # Phase 1: Force circuit to open with failures
        async def failing_operation():
            raise TTSServerError("Server error", 500)
        
        for _ in range(4):
            try:
                await error_handler.execute_with_retry(failing_operation)
            except (TTSRetryExhaustedError, TTSServerError):
                pass  # Expected failures
        assert error_handler.circuit_breaker.state == CircuitState.OPEN
        
        # Phase 2: Wait for cooldown and transition to half-open
        time.sleep(1.1)
        
        # Phase 3: Successful operations should close circuit
        async def successful_operation():
            return "recovered"
        
        # First success in half-open state
        result1 = await error_handler.execute_with_retry(successful_operation)
        assert result1 == "recovered"
        assert error_handler.circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Second success should close circuit
        result2 = await error_handler.execute_with_retry(successful_operation)
        assert result2 == "recovered"
        assert error_handler.circuit_breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_mixed_errors(self, error_handler):
        """Test circuit breaker behavior with different error types."""
        call_count = 0
        
        async def mixed_error_operation():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise TTSRateLimitError("Rate limit")
            elif call_count == 2:
                raise TTSNetworkError("Network error")
            elif call_count == 3:
                raise TTSServerError("Server error", 500)
            else:
                return "success"
        
        # Should eventually succeed after retries
        result = await error_handler.execute_with_retry(mixed_error_operation)
        assert result == "success"
        
        # Circuit should record the final success
        state = error_handler.circuit_breaker.get_state()
        assert state['window_size'] > 0


class TestCircuitBreakerFailurePatterns:
    """Test circuit breaker behavior under various failure patterns."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Provide circuit breaker for failure pattern testing."""
        config = CircuitBreakerConfig(
            failure_threshold=0.6,  # 60% threshold
            window_size=10,
            cooldown_period=2,
            success_threshold=3
        )
        return CircuitBreaker(config)
    
    def test_intermittent_failures(self, circuit_breaker):
        """Test circuit breaker with intermittent failure pattern."""
        # Pattern: S F S F S F S F S F (50% failure rate)
        pattern = [True, False, True, False, True, False, True, False, True, False]
        
        for success in pattern:
            if success:
                circuit_breaker.record_success()
            else:
                circuit_breaker.record_failure()
        
        # Should remain closed (50% < 60% threshold)
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._calculate_failure_rate() == 0.5
    
    def test_burst_failures(self, circuit_breaker):
        """Test circuit breaker with burst failure pattern."""
        # Pattern: S S S S F F F F F F (60% failure rate)
        for _ in range(4):
            circuit_breaker.record_success()
        for _ in range(6):
            circuit_breaker.record_failure()
        
        # Should open (60% >= 60% threshold)
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker._calculate_failure_rate() == 0.6
    
    def test_gradual_degradation(self, circuit_breaker):
        """Test circuit breaker with gradual degradation pattern."""
        # Start with successes, gradually add failures
        circuit_breaker.record_success()  # 0/1 = 0%
        circuit_breaker.record_success()  # 0/2 = 0%
        circuit_breaker.record_success()  # 0/3 = 0%
        circuit_breaker.record_failure()  # 1/4 = 25%
        circuit_breaker.record_failure()  # 2/5 = 40%
        circuit_breaker.record_failure()  # 3/6 = 50%
        circuit_breaker.record_failure()  # 4/7 = 57%
        
        assert circuit_breaker.state == CircuitState.CLOSED  # Still below threshold
        
        circuit_breaker.record_failure()  # 5/8 = 62.5%
        
        assert circuit_breaker.state == CircuitState.OPEN  # Should open now
    
    def test_recovery_with_occasional_failures(self, circuit_breaker):
        """Test recovery pattern with occasional failures."""
        # Force circuit to open
        for _ in range(10):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for cooldown
        time.sleep(2.1)
        
        # Transition to half-open
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Recovery pattern: S S F S S (should still close)
        circuit_breaker.record_success()  # 1 success
        circuit_breaker.record_success()  # 2 successes
        circuit_breaker.record_failure()  # Failure during recovery
        
        # Should go back to OPEN
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Try recovery again
        time.sleep(2.1)
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Successful recovery: S S S
        circuit_breaker.record_success()  # 1 success
        circuit_breaker.record_success()  # 2 successes
        circuit_breaker.record_success()  # 3 successes
        
        assert circuit_breaker.state == CircuitState.CLOSED
    
    def test_rapid_failure_recovery_cycles(self, circuit_breaker):
        """Test rapid cycles of failure and recovery."""
        for cycle in range(3):
            # Failure phase
            for _ in range(10):
                circuit_breaker.record_failure()
            
            assert circuit_breaker.state == CircuitState.OPEN
            
            # Recovery phase
            time.sleep(2.1)
            assert circuit_breaker.can_execute() is True
            
            # Successful recovery
            for _ in range(3):
                circuit_breaker.record_success()
            
            assert circuit_breaker.state == CircuitState.CLOSED
    
    def test_threshold_boundary_conditions(self, circuit_breaker):
        """Test behavior at threshold boundaries."""
        # Test exactly at threshold (60%)
        # Pattern: 6 failures, 4 successes = 60%
        for _ in range(4):
            circuit_breaker.record_success()
        for _ in range(6):
            circuit_breaker.record_failure()
        
        # Should open at exactly 60%
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker._calculate_failure_rate() == 0.6
        
        # Reset and test just below threshold
        circuit_breaker.reset()
        
        # Pattern: 5 failures, 5 successes = 50%
        for _ in range(5):
            circuit_breaker.record_success()
        for _ in range(5):
            circuit_breaker.record_failure()
        
        # Should remain closed (50% < 60%)
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._calculate_failure_rate() == 0.5


class TestTTSServiceCircuitBreakerIntegration:
    """Test circuit breaker integration with TTS service."""
    
    @pytest.fixture
    def tts_service(self):
        """Provide TTS service with circuit breaker."""
        config = TTSConfig(api_key="test_key", voice_id="test_voice")
        return TTSService(config)
    
    def test_circuit_breaker_state_reporting(self, tts_service):
        """Test circuit breaker state reporting through TTS service."""
        # Get initial state
        error_state = tts_service.get_error_state()
        assert error_state['circuit_breaker']['state'] == 'closed'
        assert error_state['circuit_breaker']['can_execute'] is True
        
        # Force some failures
        for _ in range(4):
            tts_service.error_handler.circuit_breaker.record_failure()
        
        # Check updated state
        error_state = tts_service.get_error_state()
        assert error_state['circuit_breaker']['state'] == 'open'
        assert error_state['circuit_breaker']['can_execute'] is False
    
    def test_circuit_breaker_reset_through_service(self, tts_service):
        """Test circuit breaker reset through TTS service."""
        # Force circuit to open
        for _ in range(4):
            tts_service.error_handler.circuit_breaker.record_failure()
        
        assert tts_service.error_handler.circuit_breaker.state == CircuitState.OPEN
        
        # Reset through service
        tts_service.reset_circuit_breaker()
        
        assert tts_service.error_handler.circuit_breaker.state == CircuitState.CLOSED
        error_state = tts_service.get_error_state()
        assert error_state['circuit_breaker']['state'] == 'closed'
    
    @pytest.mark.asyncio
    async def test_synthesis_blocked_by_circuit_breaker(self, tts_service):
        """Test that synthesis is blocked when circuit breaker is open."""
        # Force circuit breaker to open
        for _ in range(10):
            tts_service.error_handler.circuit_breaker.record_failure()
        
        assert tts_service.error_handler.circuit_breaker.state == CircuitState.OPEN
        
        # Synthesis should be blocked
        with pytest.raises(TTSError, match="TTS service is in error state"):
            await tts_service.synthesize_text("test text")
    
    @pytest.mark.asyncio
    async def test_recovery_attempt_integration(self, tts_service):
        """Test recovery attempt integration with circuit breaker."""
        # Force error state and open circuit
        test_error = TTSServerError("Server error", 500)
        tts_service.error_handler._update_error_state(test_error)
        
        # Mock successful recovery
        with patch.object(tts_service.error_handler, 'attempt_recovery', return_value=True):
            # Should clear error state and allow synthesis
            assert await tts_service.attempt_recovery() is True
            
            error_state = tts_service.get_error_state()
            assert error_state['has_error'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])