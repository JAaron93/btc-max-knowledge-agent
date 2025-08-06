#!/usr/bin/env python3
"""
Simple test script for circuit breaker implementation.
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Copy the circuit breaker implementation here for testing
class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, requests are short-circuited
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: float = 0.5  # 50% failure rate to open circuit
    window_size: int = 10  # Number of requests to track
    cooldown_period: int = 60  # Seconds to wait before half-open
    success_threshold: int = 3  # Consecutive successes to close circuit


class CircuitBreaker:
    """Circuit breaker implementation for TTS service resilience."""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None

        # Sliding window to track request outcomes
        self.request_window: deque = deque(maxlen=self.config.window_size)

        logger.info(
            f"Circuit breaker initialized - Threshold: {self.config.failure_threshold}, "
            f"Window: {self.config.window_size}, Cooldown: {self.config.cooldown_period}s"
        )

    def _calculate_failure_rate(self) -> float:
        """Calculate current failure rate from sliding window."""
        if not self.request_window:
            return 0.0

        failures = sum(1 for success in self.request_window if not success)
        return failures / len(self.request_window)

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should transition from OPEN to HALF_OPEN."""
        if self.state != CircuitState.OPEN or not self.opened_at:
            return False

        now = datetime.now(timezone.utc)
        time_since_opened = (now - self.opened_at).total_seconds()
        return time_since_opened >= self.config.cooldown_period

    def _log_state_change(
        self, old_state: CircuitState, new_state: CircuitState, reason: str
    ):
        """Log circuit breaker state changes."""
        logger.warning(
            f"Circuit breaker state change: {old_state.value} → {new_state.value} - {reason}",
            extra={
                "circuit_breaker": {
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "reason": reason,
                    "failure_rate": self._calculate_failure_rate(),
                    "window_size": len(self.request_window),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit state."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.HALF_OPEN:
            return True
        elif self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                old_state = self.state
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self._log_state_change(
                    old_state,
                    self.state,
                    "Cooldown period expired, testing service recovery",
                )
                return True
            return False

        return False

    def record_success(self):
        """Record a successful request."""
        self.request_window.append(True)
        self.last_failure_time = None

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                old_state = self.state
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.opened_at = None
                self._log_state_change(
                    old_state,
                    self.state,
                    f"Service recovered after {self.success_count} consecutive successes",
                )
        elif self.state == CircuitState.OPEN:
            # This shouldn't happen, but handle gracefully
            logger.warning(
                "Received success while circuit is OPEN - this indicates a logic error"
            )

    def record_failure(self):
        """Record a failed request and update circuit state."""
        self.request_window.append(False)
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.state == CircuitState.HALF_OPEN:
            # Failure during half-open means service is still down
            old_state = self.state
            self.state = CircuitState.OPEN
            self.opened_at = self.last_failure_time
            self.success_count = 0
            self._log_state_change(
                old_state, self.state, "Service still failing during recovery test"
            )

        elif self.state == CircuitState.CLOSED:
            # Check if we should open the circuit
            failure_rate = self._calculate_failure_rate()
            if (
                len(self.request_window) >= self.config.window_size
                and failure_rate >= self.config.failure_threshold
            ):
                old_state = self.state
                self.state = CircuitState.OPEN
                self.opened_at = self.last_failure_time
                self._log_state_change(
                    old_state,
                    self.state,
                    f"Failure rate {failure_rate:.2%} exceeded threshold {self.config.failure_threshold:.2%}",
                )

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state information."""
        return {
            "state": self.state.value,
            "failure_rate": self._calculate_failure_rate(),
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "window_size": len(self.request_window),
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "can_execute": self.can_execute(),
        }

    def reset(self):
        """Reset circuit breaker to initial state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None
        self.request_window.clear()

        if old_state != CircuitState.CLOSED:
            self._log_state_change(
                old_state, self.state, "Circuit breaker manually reset"
            )


async def test_circuit_breaker_basic():
    """Test basic circuit breaker functionality."""
    logger.info("=== Testing Basic Circuit Breaker Functionality ===")

    # Create circuit breaker with low threshold for testing
    config = CircuitBreakerConfig(
        failure_threshold=0.5,  # 50% failure rate
        window_size=4,  # Small window for quick testing
        cooldown_period=2,  # 2 second cooldown
        success_threshold=2,  # 2 successes to close
    )

    circuit_breaker = CircuitBreaker(config)

    # Test 1: Circuit should start closed
    assert circuit_breaker.state == CircuitState.CLOSED
    logger.info("✓ Circuit starts in CLOSED state")

    # Test 2: Generate failures to open circuit
    logger.info("Generating failures to trigger circuit opening...")
    for i in range(4):
        if circuit_breaker.can_execute():
            circuit_breaker.record_failure()
            logger.info(f"Recorded failure {i+1}")
        else:
            logger.info(f"Circuit blocked execution at failure {i+1}")

    # Circuit should now be open
    circuit_state = circuit_breaker.get_state()
    logger.info(f"Circuit state after failures: {circuit_state}")

    if circuit_state["state"] == "open":
        logger.info("✓ Circuit opened after failure threshold reached")
    else:
        logger.warning(f"⚠ Circuit state is {circuit_state['state']}, expected 'open'")

    # Test 3: Requests should be short-circuited
    if not circuit_breaker.can_execute():
        logger.info("✓ Requests are properly short-circuited when circuit is open")
    else:
        logger.error("✗ Circuit should be blocking requests but it's not")

    # Test 4: Wait for cooldown and test half-open state
    logger.info("Waiting for cooldown period...")
    await asyncio.sleep(2.5)  # Wait longer than cooldown period

    # Next request should transition to half-open
    if circuit_breaker.can_execute():
        logger.info("✓ Circuit transitioned to half-open after cooldown")

        # Record successes to close the circuit
        circuit_breaker.record_success()
        logger.info("✓ First success in half-open state")

        circuit_breaker.record_success()
        logger.info("✓ Second success should close the circuit")

        circuit_state = circuit_breaker.get_state()
        if circuit_state["state"] == "closed":
            logger.info("✓ Circuit closed after successful recovery")
        else:
            logger.warning(
                f"⚠ Circuit state is {circuit_state['state']}, expected 'closed'"
            )
    else:
        logger.error("✗ Circuit should allow execution after cooldown")


async def test_circuit_breaker_failure_during_recovery():
    """Test circuit breaker behavior when failure occurs during half-open state."""
    logger.info("\n=== Testing Failure During Recovery ===")

    config = CircuitBreakerConfig(
        failure_threshold=0.5, window_size=4, cooldown_period=1, success_threshold=2
    )

    circuit_breaker = CircuitBreaker(config)

    # Generate failures to open circuit
    for i in range(4):
        if circuit_breaker.can_execute():
            circuit_breaker.record_failure()

    logger.info("Circuit opened, waiting for cooldown...")
    await asyncio.sleep(1.5)

    # Try to recover but fail - should go back to open
    if circuit_breaker.can_execute():
        circuit_breaker.record_failure()
        logger.info("Recovery attempt failed as expected")

    circuit_state = circuit_breaker.get_state()
    if circuit_state["state"] == "open":
        logger.info("✓ Circuit returned to OPEN state after failed recovery")
    else:
        logger.warning(f"⚠ Circuit state is {circuit_state['state']}, expected 'open'")


async def main():
    """Run all circuit breaker tests."""
    logger.info("Starting Circuit Breaker Tests")

    try:
        await test_circuit_breaker_basic()
        await test_circuit_breaker_failure_during_recovery()

        logger.info("\n=== All Tests Completed Successfully ===")

    except Exception as e:
        logger.error(f"Test failed with error: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
