#!/usr/bin/env python3
"""
Pure Exponential Backoff Helper

This module provides a simple, pure function for exponential backoff calculations
with a reasonable ceiling and reset logic for successful long-running execution.
"""

from __future__ import annotations

import logging
from typing import Final

# Configure logging
logging.basicConfig(level=logging.INFO)

# Constants
DEFAULT_INITIAL_DELAY: Final[float] = 1.0  # seconds
DEFAULT_MAX_DELAY: Final[float] = 300.0  # 5 minutes in seconds
DEFAULT_MULTIPLIER: Final[float] = 2.0


def next_backoff(
    prev: float,
    multiplier: float = DEFAULT_MULTIPLIER,
    max_delay: float = DEFAULT_MAX_DELAY,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
) -> float:
    """
    Calculate the next exponential backoff delay.

    This is a pure function that doubles the delay up to a sane ceiling (5 minutes by default)
    and resets on successful long-running execution.

    The function implements exponential backoff by multiplying the previous delay by the
    multiplier (default 2.0), capping it at the maximum delay.

    Args:
        prev: Previous delay in seconds. If 0 or negative, returns initial_delay.
        multiplier: Multiplier for exponential backoff (default: 2.0)
        max_delay: Maximum delay ceiling in seconds (default: 300.0 = 5 minutes)
        initial_delay: Initial delay when starting fresh (default: 1.0 second)

    Returns:
        Next delay in seconds, capped at max_delay

    Examples:
        >>> next_backoff(0)  # Starting fresh
        1.0
        >>> next_backoff(1.0)  # First retry
        2.0
        >>> next_backoff(2.0)  # Second retry
        4.0
        >>> next_backoff(8.0)  # Third retry
        16.0
        >>> next_backoff(200.0)  # Near ceiling
        300.0
        >>> next_backoff(300.0)  # At ceiling
        300.0
    """
    # Reset to initial delay if prev is 0 or negative (fresh start)
    if prev <= 0:
        return initial_delay

    # Calculate next delay with exponential backoff
    next_delay = prev * multiplier

    # Cap at maximum delay
    return min(next_delay, max_delay)


def reset_backoff() -> float:
    """
    Reset backoff to initial delay for successful long-running execution.

    This function should be called after a successful operation that ran for
    a sufficient duration, indicating the system has recovered.

    Returns:
        Initial delay value

    Examples:
        >>> reset_backoff()
        1.0
    """
    return DEFAULT_INITIAL_DELAY


def backoff_sequence(
    max_attempts: int = 10,
    multiplier: float = DEFAULT_MULTIPLIER,
    max_delay: float = DEFAULT_MAX_DELAY,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
) -> list[float]:
    """
    Generate a complete backoff sequence for a given number of attempts.

    This utility function helps visualize and test the backoff progression.

    Args:
        max_attempts: Maximum number of retry attempts
        multiplier: Multiplier for exponential backoff
        max_delay: Maximum delay ceiling in seconds
        initial_delay: Initial delay when starting fresh

    Returns:
        List of delays for each attempt

    Examples:
        >>> backoff_sequence(5)
        [1.0, 2.0, 4.0, 8.0, 16.0]
        >>> backoff_sequence(3, multiplier=3.0, initial_delay=0.5)
        [0.5, 1.5, 4.5]
    """
    sequence: list[float] = []
    current_delay: float = 0.0  # Start with 0 to trigger initial delay

    for _ in range(max_attempts):
        current_delay = next_backoff(
            current_delay, multiplier, max_delay, initial_delay
        )
        sequence.append(current_delay)

    return sequence


def total_backoff_time(
    max_attempts: int = 10,
    multiplier: float = DEFAULT_MULTIPLIER,
    max_delay: float = DEFAULT_MAX_DELAY,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
) -> float:
    """
    Calculate total time spent in backoff delays for a given number of attempts.

    This utility function helps estimate the total time impact of retry operations.

    Args:
        max_attempts: Maximum number of retry attempts
        multiplier: Multiplier for exponential backoff
        max_delay: Maximum delay ceiling in seconds
        initial_delay: Initial delay when starting fresh

    Returns:
        Total delay time in seconds

    Examples:
        >>> total_backoff_time(4)  # 1.0 + 2.0 + 4.0 + 8.0
        15.0
    """
    return sum(backoff_sequence(max_attempts, multiplier, max_delay, initial_delay))


# For backward compatibility and convenience
calculate_next_backoff = next_backoff
