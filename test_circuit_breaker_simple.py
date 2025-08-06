#!/usr/bin/env python3
"""
Simple test script for circuit breaker implementation.
"""

import asyncio
import logging
from datetime import datetime, timezone
from freezegun import freeze_time
from typing import Any, Dict, Optional

# Import CircuitBreaker and related classes from production code
from src.utils.tts_error_handler import CircuitBreaker, CircuitBreakerConfig, CircuitState

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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

    # Test initial state
    state = circuit_breaker.get_state()
    assert state["state"] == "closed"
    assert state["failure_count"] == 0
    assert circuit_breaker.can_execute()
    logger.info("✓ Circuit breaker starts in CLOSED state")

    # Test successful requests
    for i in range(2):
        assert circuit_breaker.can_execute()
        circuit_breaker.record_success()
        logger.info(f"✓ Recorded success {i + 1}")

    state = circuit_breaker.get_state()
    assert state["state"] == "closed"
    logger.info("✓ Circuit remains CLOSED after successes")

    # Test failures to trigger opening
    for i in range(3):  # 3 failures out of 4 requests = 75% failure rate
        assert circuit_breaker.can_execute()
        circuit_breaker.record_failure()
        logger.info(f"✓ Recorded failure {i + 1}")

    state = circuit_breaker.get_state()
    assert state["state"] == "open"
    assert not circuit_breaker.can_execute()
    logger.info("✓ Circuit OPENED after exceeding failure threshold")

    # Test that requests are blocked in OPEN state
    assert not circuit_breaker.can_execute()
    logger.info("✓ Requests blocked in OPEN state")

    # Test transition to HALF_OPEN after cooldown
    logger.info("Waiting for cooldown period...")
    with freeze_time() as frozen_time:
        frozen_time.tick(delta=3)  # Advance time by 3 seconds
        assert circuit_breaker.can_execute()
        state = circuit_breaker.get_state()
        assert state["state"] == "half_open"
        logger.info("✓ Circuit transitioned to HALF_OPEN after cooldown")

    # Test recovery with successful requests
    circuit_breaker.record_success()
    logger.info("✓ First success in HALF_OPEN state")

    circuit_breaker.record_success()
    state = circuit_breaker.get_state()
    assert state["state"] == "closed"
    logger.info("✓ Circuit CLOSED after sufficient successes")

    logger.info("=== Basic Circuit Breaker Test Completed Successfully ===\n")


async def test_circuit_breaker_failure_during_recovery():
    """Test circuit breaker behavior when failure occurs during half-open state."""
    logger.info("\n=== Testing Failure During Recovery ===")

    config = CircuitBreakerConfig(
        failure_threshold=0.5,
        window_size=4,
        cooldown_period=1,
        success_threshold=2,
    )

    circuit_breaker = CircuitBreaker(config)

    # Force circuit to OPEN state
    for _ in range(3):
        circuit_breaker.record_failure()

    state = circuit_breaker.get_state()
    assert state["state"] == "open"
    logger.info("✓ Circuit forced to OPEN state")

    # Wait for cooldown and transition to HALF_OPEN
    with freeze_time() as frozen_time:
        frozen_time.tick(delta=2)
        assert circuit_breaker.can_execute()
        state = circuit_breaker.get_state()
        assert state["state"] == "half_open"
        logger.info("✓ Circuit transitioned to HALF_OPEN")

    # Record a failure during HALF_OPEN - should immediately open circuit
    circuit_breaker.record_failure()
    state = circuit_breaker.get_state()
    assert state["state"] == "open"
    assert not circuit_breaker.can_execute()
    logger.info("✓ Circuit immediately OPENED after failure in HALF_OPEN state")

    logger.info("=== Failure During Recovery Test Completed Successfully ===\n")


async def main():
    """Run all circuit breaker tests."""
    logger.info("🚀 Starting Circuit Breaker Tests")
    logger.info("=" * 50)

    try:
        await test_circuit_breaker_basic()
        await test_circuit_breaker_failure_during_recovery()

        logger.info("🎉 All circuit breaker tests passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)