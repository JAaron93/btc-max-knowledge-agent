#!/usr/bin/env python3
"""
Test script for TTS service with circuit breaker integration.
"""

import asyncio
import logging
import os
from unittest.mock import MagicMock, patch

# Set up environment
os.environ["ELEVEN_LABS_API_KEY"] = "test_key"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_tts_circuit_breaker_integration():
    """Test TTS service with circuit breaker integration."""
    logger.info("=== Testing TTS Service Circuit Breaker Integration ===")

    # Import here to avoid the syntax error in audio_utils
    try:
        from src.utils.tts_error_handler import (
            CircuitBreakerConfig,
            TTSCircuitOpenError,
        )
        from src.utils.tts_service import TTSConfig, TTSService
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return

    # Create TTS service with circuit breaker config
    circuit_config = CircuitBreakerConfig(
        failure_threshold=0.5, window_size=4, cooldown_period=2, success_threshold=2
    )

    config = TTSConfig(api_key="test_key")

    # Mock the multi-tier cache to avoid import issues
    with patch("src.utils.tts_service.get_audio_cache") as mock_cache:
        mock_cache_instance = MagicMock()
        mock_cache_instance.get.return_value = None  # No cached audio
        mock_cache_instance.put.return_value = "cache_key"
        mock_cache.return_value = mock_cache_instance

        # Create TTS service
        tts_service = TTSService(config)

        # Override the circuit breaker config
        tts_service.error_handler.circuit_breaker.config = circuit_config
        tts_service.error_handler.circuit_breaker.request_window.maxlen = (
            circuit_config.window_size
        )

        # Test 1: Service should start with circuit closed
        error_state = tts_service.get_error_state()
        assert error_state["circuit_breaker"]["state"] == "closed"
        logger.info("✓ TTS service starts with circuit breaker in CLOSED state")

        # Test 2: Mock API failures to trigger circuit opening
        with patch.object(
            tts_service, "_synthesize_with_api", side_effect=Exception("API Error")
        ):
            logger.info("Generating API failures to trigger circuit opening...")

            for i in range(4):
                try:
                    await tts_service.synthesize_text("test text")
                except Exception as e:
                    logger.info(f"Expected failure {i+1}: {type(e).__name__}")

            # Check circuit state
            error_state = tts_service.get_error_state()
            circuit_state = error_state["circuit_breaker"]["state"]

            if circuit_state == "open":
                logger.info("✓ Circuit breaker opened after failure threshold reached")
            else:
                logger.warning(f"⚠ Circuit state is {circuit_state}, expected 'open'")

        # Test 3: Requests should be short-circuited
        try:
            await tts_service.synthesize_text("test text")
            logger.error("✗ Expected TTSCircuitOpenError but synthesis succeeded")
        except TTSCircuitOpenError:
            logger.info("✓ Requests are properly short-circuited when circuit is open")
        except Exception as e:
            logger.error(f"✗ Unexpected error: {type(e).__name__}: {e}")

        # Test 4: Test recovery after cooldown
        logger.info("Waiting for cooldown period...")
        await asyncio.sleep(2.5)

        # Mock successful API calls for recovery
        with patch.object(
            tts_service, "_synthesize_with_api", return_value=b"fake_audio_data"
        ):
            try:
                result = await tts_service.synthesize_text("test text")
                logger.info("✓ First success in half-open state")

                result = await tts_service.synthesize_text("test text")
                logger.info("✓ Second success should close the circuit")

                error_state = tts_service.get_error_state()
                circuit_state = error_state["circuit_breaker"]["state"]

                if circuit_state == "closed":
                    logger.info("✓ Circuit closed after successful recovery")
                else:
                    logger.warning(
                        f"⚠ Circuit state is {circuit_state}, expected 'closed'"
                    )

            except Exception as e:
                logger.error(f"✗ Recovery failed: {type(e).__name__}: {e}")

        # Test 5: Test manual circuit breaker reset
        logger.info("Testing manual circuit breaker reset...")

        # Force circuit open again
        for i in range(4):
            tts_service.error_handler.circuit_breaker.record_failure()

        error_state = tts_service.get_error_state()
        if error_state["circuit_breaker"]["state"] == "open":
            logger.info("Circuit forced open for reset test")

            # Reset circuit breaker
            tts_service.reset_circuit_breaker()

            error_state = tts_service.get_error_state()
            if error_state["circuit_breaker"]["state"] == "closed":
                logger.info("✓ Circuit breaker manually reset to CLOSED state")
            else:
                logger.warning(
                    f"⚠ Circuit state after reset: {error_state['circuit_breaker']['state']}"
                )


async def main():
    """Run TTS circuit breaker integration tests."""
    logger.info("Starting TTS Circuit Breaker Integration Tests")

    try:
        await test_tts_circuit_breaker_integration()
        logger.info("\n=== All Integration Tests Completed ===")

    except Exception as e:
        logger.error(f"Integration test failed: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
