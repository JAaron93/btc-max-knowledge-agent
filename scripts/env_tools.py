"""Environment variable helper with safety checks and logging.

This module provides utilities for safely setting environment variables with
proper logging and override controls to prevent silent modifications.
"""

import logging
import os
from typing import Optional, Union

logger = logging.getLogger(__name__)


def set_env_var(
    key: str, value: Union[str, int, float, bool], allow_override: bool = False
) -> bool:
    """Set environment variable with safety checks and logging.

    Args:
        key: Environment variable name
        value: Value to set (will be converted to string)
        allow_override: Whether to allow overriding existing variables

    Returns:
        True if variable was set, False if skipped

    Raises:
        TypeError: If key is not a string
        ValueError: If key is empty or None
    """
    if not isinstance(key, str):
        raise TypeError(f"Environment variable key must be a string, got {type(key)}")

    # Normalize the key: strip whitespace and convert to uppercase
    key = key.strip().upper()
    if not key:
        raise ValueError("Environment variable key cannot be empty")

    # Convert value to string
    str_value = str(value)

    # Check if variable already exists
    existing_value = os.environ.get(key)

    if existing_value is not None:
        if not allow_override:
            logger.warning(
                f"Environment variable '{key}' already exists with value '{existing_value}'. "
                f"Skipping assignment of '{str_value}'. Use allow_override=True to override."
            )
            return False
        else:
            logger.warning(
                f"Overriding environment variable '{key}' from '{existing_value}' to '{str_value}'"
            )

    # Set the environment variable
    os.environ[key] = str_value
    logger.info(f"Set environment variable '{key}' = '{str_value}'")
    return True


def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable value.

    Args:
        key: Environment variable name
        default: Default value if variable doesn't exist

    Returns:
        Environment variable value or default

    Raises:
        TypeError: If key is not a string
        ValueError: If key is empty or None
    """
    if not isinstance(key, str):
        raise TypeError(f"Environment variable key must be a string, got {type(key)}")

    # Normalize the key: strip whitespace and convert to uppercase
    key = key.strip().upper()
    if not key:
        raise ValueError("Environment variable key cannot be empty")

    return os.environ.get(key, default)


def unset_env_var(key: str) -> bool:
    """Remove environment variable if it exists.

    Args:
        key: Environment variable name

    Returns:
        True if variable was removed, False if it didn't exist

    Raises:
        TypeError: If key is not a string
        ValueError: If key is empty or None
    """
    if not isinstance(key, str):
        raise TypeError(f"Environment variable key must be a string, got {type(key)}")

    # Normalize the key: strip whitespace and convert to uppercase
    key = key.strip().upper()
    if not key:
        raise ValueError("Environment variable key cannot be empty")

    if key in os.environ:
        del os.environ[key]
        logger.info(f"Removed environment variable '{key}'")
        return True

    return False
