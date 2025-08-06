"""
Shared validation utilities for the BTC Max Knowledge Agent
"""


def validate_volume(volume):
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


def validate_volume_strict(volume):
    """
    Validate volume with strict error raising.

    Args:
        volume: Volume value to validate

    Raises:
        ValueError: If volume is not None and outside valid range

    Returns:
        bool: True if validation passes
    """
    if not validate_volume(volume):
        raise ValueError(f"Volume must be between 0.0 and 1.0, got {volume}")
    return True
