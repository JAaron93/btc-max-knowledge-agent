"""
Shared validation utilities for the BTC Max Knowledge Agent
"""

from typing import Optional


def validate_volume(volume: Optional[float]) -> bool:
    """
    Validate that volume is within the acceptable range.

    Args:
        volume: Volume value to validate (can be None)

    Returns:
        bool: True if volume is valid (None or 0.0-1.0), False otherwise
    """
    if volume is None:
        return True
    return 0.0 <= volume <= 1.0


def validate_volume_strict(volume: Optional[float]) -> bool:
    """
    Validate volume with strict error raising.

    Args:
        volume (Optional[float]): Volume value to validate. May be None.

    Raises:
        ValueError: If volume is not None and outside the inclusive range
                    [0.0, 1.0].

    Returns:
        bool: True if validation passes (i.e., volume is None or within 0.0 to 1.0).
    """
    if volume is not None and not 0.0 <= volume <= 1.0:
        raise ValueError(f"Volume must be between 0.0 and 1.0, got {volume}")
    return True
