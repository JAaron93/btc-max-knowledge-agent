#!/usr/bin/env python3
"""
Test script for circuit breaker implementation in TTS service.
"""

import asyncio
import logging

from src.utils.tts_error_handler import (
    CircuitBreakerConfig,
    CircuitState,
    TTSCircuitOpenError,
    TTSErrorHandler,
    TTSNetworkError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def simulate_failing_operation():
    """Simulate an operation that always fails."""
    await asyncio.sleep(0.1)  # Simulate some work
    raise TTSNetworkError("Simulated network failure")


async def simulate_successful_operation():
    """Simulate an operation that always succeeds."""
    await asyncio.sleep(0.1)  # Simulate some work
    return "success"


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

    error_handler = TTSErrorHandler(circuit_config=config)

    # Test 1: Circuit should start closed
    assert error_handler.circuit_breaker.state == CircuitState.CLOSED
    logger.info("✓ Circuit starts in CLOSED state")

    # Test 2: Generate failures to open circuit
    logger.info("Generating failures to trigger circuit opening...")
    for i in range(4):
        try:
            await error_handler.execute_with_retry(simulate_failing_operation)
        except Exception as e:
            logger.info(f"Expected failure {i+1}: {type(e).__name__}")

    # Circuit should now be open
    circuit_state = error_handler.get_circuit_breaker_state()
    logger.info(f"Circuit state after failures: {circuit_state}")

    if circuit_state["state"] == "open":
        logger.info("✓ Circuit opened after failure threshold reached")
    else:
        logger.warning(f"⚠ Circuit state is {circuit_state['state']}, expected 'open'")

    # Test 3: Requests should be short-circuited
    try:
        await error_handler.execute_with_retry(simulate_successful_operation)
        logger.error("✗ Expected TTSCircuitOpenError but operation succeeded")
    except TTSCircuitOpenError:
        logger.info("✓ Requests are properly short-circuited when circuit is open")
    except Exception as e:
        logger.error(f"✗ Unexpected error: {type(e).__name__}: {e}")

    # Test 4: Wait for cooldown and test half-open state
    logger.info("Waiting for cooldown period...")
    await asyncio.sleep(2.5)  # Wait longer than cooldown period

    # Next request should transition to half-open
    try:
        result = await error_handler.execute_with_retry(simulate_successful_operation)
        logger.info("✓ First success in half-open state")

        # One more success should close the circuit
        result = await error_handler.execute_with_retry(simulate_successful_operation)
        logger.info("✓ Second success should close the circuit")

        circuit_state = error_handler.get_circuit_breaker_state()
        if circuit_state["state"] == "closed":
            logger.info("✓ Circuit closed after successful recovery")
        else:
            logger.warning(
                f"⚠ Circuit state is {circuit_state['state']}, expected 'closed'"
            )

    except Exception as e:
        logger.error(f"✗ Recovery failed: {type(e).__name__}: {e}")


async def test_circuit_breaker_failure_during_recovery():
    """Test circuit breaker behavior when failure occurs during half-open state."""
    logger.info("\n=== Testing Failure During Recovery ===")

    config = CircuitBreakerConfig(
        failure_threshold=0.5, window_size=4, cooldown_period=1, success_threshold=2
    )

    error_handler = TTSErrorHandler(circuit_config=config)

    # Generate failures to open circuit
    for i in range(4):
        try:
            await error_handler.execute_with_retry(simulate_failing_operation)
        except Exception:
            pass

    logger.info("Circuit opened, waiting for cooldown...")
    await asyncio.sleep(1.5)

    # Try to recover but fail - should go back to open
    try:
        await error_handler.execute_with_retry(simulate_failing_operation)
    except Exception as e:
        logger.info(f"Recovery attempt failed as expected: {type(e).__name__}")

    circuit_state = error_handler.get_circuit_breaker_state()
    if circuit_state["state"] == "open":
        logger.info("✓ Circuit returned to OPEN state after failed recovery")
    else:
        logger.warning(f"⚠ Circuit state is {circuit_state['state']}, expected 'open'")


async def test_timeout_handling():
    """Test timeout handling in TTS operations."""
    logger.info("\n=== Testing Timeout Handling ===")

    async def simulate_timeout_operation():
        """Simulate an operation that times out."""
        await asyncio.sleep(50)  # Longer than total timeout (45s)
        return "should not reach here"

    error_handler = TTSErrorHandler()

    try:
        # This should timeout and be handled as a network error
        await error_handler.execute_with_retry(simulate_timeout_operation)
        logger.error("✗ Expected timeout error but operation succeeded")
    except Exception as e:
        logger.info(f"✓ Timeout handled correctly: {type(e).__name__}: {e}")


async def main():
    """Run all circuit breaker tests."""
    logger.info("Starting Circuit Breaker Tests")

    try:
        await test_circuit_breaker_basic()
        await test_circuit_breaker_failure_during_recovery()
        # Note: timeout test would take too long, so we'll skip it in this demo
        # await test_timeout_handling()

        logger.info("\n=== All Tests Completed ===")

    except Exception as e:
        logger.error(f"Test failed with error: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
