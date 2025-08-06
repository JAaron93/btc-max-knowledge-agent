#!/usr/bin/env python3
"""
Unit tests for exponential backoff utility functions.

This module tests the pure exponential backoff helper functions,
ensuring proper doubling behavior, ceiling enforcement, and reset logic.
"""

import unittest

# Import path is configured in tests/conftest.py; import directly
from utils.exponential_backoff import (
    DEFAULT_INITIAL_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_MULTIPLIER,
    backoff_sequence,
    next_backoff,
    reset_backoff,
    total_backoff_time,
)


class TestExponentialBackoff(unittest.TestCase):
    """Test the exponential backoff utility functions."""

    def test_next_backoff_basic_functionality(self):
        """Test the basic exponential doubling behavior."""
        # Starting fresh (0 or negative should return initial delay)
        self.assertEqual(next_backoff(0), 1.0)
        self.assertEqual(next_backoff(-1.0), 1.0)
        self.assertEqual(next_backoff(-5.5), 1.0)

        # Basic doubling sequence
        self.assertEqual(next_backoff(1.0), 2.0)
        self.assertEqual(next_backoff(2.0), 4.0)
        self.assertEqual(next_backoff(4.0), 8.0)
        self.assertEqual(next_backoff(8.0), 16.0)
        self.assertEqual(next_backoff(16.0), 32.0)
        self.assertEqual(next_backoff(32.0), 64.0)
        self.assertEqual(next_backoff(64.0), 128.0)

    def test_next_backoff_ceiling_enforcement(self):
        """Test that the backoff is capped at the maximum delay."""
        # Test with default ceiling (300 seconds = 5 minutes)
        # 200 * 2 = 400, capped to 300
        self.assertEqual(next_backoff(200.0), 300.0)
        # 250 * 2 = 500, capped to 300
        self.assertEqual(next_backoff(250.0), 300.0)
        # Already at ceiling
        self.assertEqual(next_backoff(300.0), 300.0)
        # Above ceiling, still capped
        self.assertEqual(next_backoff(500.0), 300.0)

        # Test with custom ceiling
        self.assertEqual(
            next_backoff(50.0, max_delay=60.0), 60.0
        )  # 50 * 2 = 100, capped to 60
        self.assertEqual(
            next_backoff(30.0, max_delay=60.0), 60.0
        )  # 30 * 2 = 60, at ceiling
        self.assertEqual(
            next_backoff(25.0, max_delay=60.0), 50.0
        )  # 25 * 2 = 50, under ceiling

    def test_next_backoff_custom_parameters(self):
        """Test next_backoff with custom multiplier and initial delay."""
        # Custom multiplier (3x instead of 2x)
        self.assertEqual(next_backoff(1.0, multiplier=3.0), 3.0)
        self.assertEqual(next_backoff(2.0, multiplier=3.0), 6.0)
        self.assertEqual(next_backoff(5.0, multiplier=3.0), 15.0)

        # Custom initial delay
        self.assertEqual(next_backoff(0, initial_delay=0.5), 0.5)
        self.assertEqual(next_backoff(-1, initial_delay=2.0), 2.0)

        # Combined custom parameters
        self.assertEqual(
            next_backoff(0, multiplier=1.5, initial_delay=0.8),
            0.8,
        )
        self.assertEqual(next_backoff(2.0, multiplier=1.5), 3.0)

    def test_next_backoff_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Very small values
        self.assertEqual(next_backoff(0.1), 0.2)
        self.assertEqual(next_backoff(0.01), 0.02)

        # Large values near ceiling
        self.assertEqual(next_backoff(149.9), 299.8)
        self.assertEqual(next_backoff(150.0), 300.0)  # Exactly at threshold
        self.assertEqual(next_backoff(150.1), 300.0)  # Just over threshold

        # Multiplier of 1 (no growth)
        self.assertEqual(next_backoff(5.0, multiplier=1.0), 5.0)
        self.assertEqual(next_backoff(10.0, multiplier=1.0), 10.0)

        # Very large multiplier
        self.assertEqual(
            next_backoff(1.0, multiplier=100.0, max_delay=1000.0),
            100.0,
        )
        self.assertEqual(
            next_backoff(10.0, multiplier=100.0, max_delay=500.0),
            500.0,
        )

    def test_reset_backoff(self):
        """Test the reset_backoff function."""
        self.assertEqual(reset_backoff(), DEFAULT_INITIAL_DELAY)
        self.assertEqual(reset_backoff(), 1.0)

    def test_backoff_sequence_default(self):
        """Test backoff_sequence with default parameters."""
        # Test various sequence lengths
        self.assertEqual(backoff_sequence(1), [1.0])
        self.assertEqual(backoff_sequence(2), [1.0, 2.0])
        self.assertEqual(backoff_sequence(3), [1.0, 2.0, 4.0])
        self.assertEqual(backoff_sequence(5), [1.0, 2.0, 4.0, 8.0, 16.0])

        # Test longer sequence with ceiling
        sequence = backoff_sequence(12)
        expected = [
            1.0,
            2.0,
            4.0,
            8.0,
            16.0,
            32.0,
            64.0,
            128.0,
            256.0,
            300.0,
            300.0,
            300.0,
        ]
        self.assertEqual(sequence, expected)

    def test_backoff_sequence_custom_parameters(self):
        """Test backoff_sequence with custom parameters."""
        # Custom multiplier
        sequence = backoff_sequence(3, multiplier=3.0, initial_delay=0.5)
        expected = [0.5, 1.5, 4.5]
        self.assertEqual(sequence, expected)

        # Custom ceiling
        sequence = backoff_sequence(8, max_delay=10.0)
        expected = [1.0, 2.0, 4.0, 8.0, 10.0, 10.0, 10.0, 10.0]
        self.assertEqual(sequence, expected)

        # All custom parameters
        sequence = backoff_sequence(
            4,
            multiplier=1.5,
            max_delay=5.0,
            initial_delay=0.8,
        )
        expected = [0.8, 1.2, 1.8, 2.7]
        # Use assertAlmostEqual for floating point comparison
        self.assertEqual(len(sequence), len(expected))
        for actual, expected_val in zip(sequence, expected):
            self.assertAlmostEqual(actual, expected_val, places=10)

    def test_backoff_sequence_edge_cases(self):
        """Test edge cases for backoff_sequence."""
        # Zero attempts
        self.assertEqual(backoff_sequence(0), [])

        # Single attempt
        self.assertEqual(backoff_sequence(1), [1.0])

        # Very large number of attempts (should quickly hit ceiling)
        sequence = backoff_sequence(20, max_delay=10.0)
        # After hitting ceiling at index 3 (8.0 -> 10.0), all should be 10.0
        self.assertTrue(all(delay == 10.0 for delay in sequence[4:]))
        self.assertEqual(len(sequence), 20)

    def test_total_backoff_time(self):
        """Test total_backoff_time calculation."""
        # Simple cases
        self.assertEqual(total_backoff_time(1), 1.0)  # Just initial delay
        self.assertEqual(total_backoff_time(2), 3.0)  # 1.0 + 2.0
        self.assertEqual(total_backoff_time(3), 7.0)  # 1.0 + 2.0 + 4.0
        self.assertEqual(total_backoff_time(4), 15.0)  # 1.0 + 2.0 + 4.0 + 8.0

        # With custom parameters
        total = total_backoff_time(3, multiplier=3.0, initial_delay=0.5)
        expected = 0.5 + 1.5 + 4.5  # 6.5
        self.assertEqual(total, expected)

        # With ceiling effects
        total = total_backoff_time(5, max_delay=10.0)
        expected = 1.0 + 2.0 + 4.0 + 8.0 + 10.0  # 25.0
        self.assertEqual(total, expected)

    def test_constants(self):
        """Test that the exported constants have expected values."""
        self.assertEqual(DEFAULT_INITIAL_DELAY, 1.0)
        self.assertEqual(DEFAULT_MAX_DELAY, 300.0)  # 5 minutes
        self.assertEqual(DEFAULT_MULTIPLIER, 2.0)

    def test_pure_function_behavior(self):
        """Test that functions are pure (no side effects)."""
        # Multiple calls with same input should return same output
        for _ in range(10):
            self.assertEqual(next_backoff(5.0), 10.0)
            self.assertEqual(reset_backoff(), 1.0)
            self.assertEqual(backoff_sequence(3), [1.0, 2.0, 4.0])

        # Functions should not modify their inputs
        prev_value = 5.0
        original_prev = prev_value
        result = next_backoff(prev_value)
        self.assertEqual(prev_value, original_prev)  # Input unchanged
        self.assertEqual(result, 10.0)  # Expected output

    def test_realistic_scenarios(self):
        """Test realistic usage scenarios."""
        # Simulate a typical retry sequence
        current_delay = 0  # Start fresh
        delays = []

        for _ in range(8):  # 8 retry attempts
            current_delay = next_backoff(current_delay)
            delays.append(current_delay)

        expected = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0]
        self.assertEqual(delays, expected)

        # Total time would be sum of delays
        total_time = sum(delays)
        self.assertEqual(total_time, 255.0)  # 1+2+4+8+16+32+64+128

        # Reset after success and start again
        current_delay = reset_backoff()  # Reset to initial
        self.assertEqual(current_delay, 1.0)

        # Next retry starts from initial delay again
        next_delay = next_backoff(current_delay)
        self.assertEqual(next_delay, 2.0)


if __name__ == "__main__":
    unittest.main()
