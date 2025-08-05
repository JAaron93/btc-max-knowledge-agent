#!/usr/bin/env python3
"""Example usage of the env_tools module."""

import logging

from env_tools import get_env_var, set_env_var, unset_env_var

# Configure logging to see the warning messages
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


def main():
    """Demonstrate the env_tools functionality."""
    print("=== Environment Variable Helper Demo ===\n")

    # 1. Setting when variable is absent
    print("1. Setting when variable is absent:")
    result = set_env_var("API_URL", "https://api.example.com")
    print(f"   Result: {result}")
    print(f"   Value: {get_env_var('API_URL')}\n")

    # 2. Skipping with warning when present
    print("2. Skipping with warning when present:")
    result = set_env_var("API_URL", "https://different-api.com")
    print(f"   Result: {result}")
    print(f"   Value: {get_env_var('API_URL')}\n")

    # 3. Overriding when allow_override=True
    print("3. Overriding when allow_override=True:")
    result = set_env_var("API_URL", "https://override-api.com", allow_override=True)
    print(f"   Result: {result}")
    print(f"   Value: {get_env_var('API_URL')}\n")

    # 4. Working with different data types
    print("4. Working with different data types:")
    set_env_var("PORT", 8080)
    set_env_var("DEBUG", True)
    set_env_var("TIMEOUT", 30.5)
    print(f"   PORT: {get_env_var('PORT')} (type: {type(get_env_var('PORT'))})")
    print(f"   DEBUG: {get_env_var('DEBUG')} (type: {type(get_env_var('DEBUG'))})")
    print(
        f"   TIMEOUT: {get_env_var('TIMEOUT')} (type: {type(get_env_var('TIMEOUT'))})\n"
    )

    # 5. Using defaults
    print("5. Using defaults for non-existent variables:")
    value = get_env_var("NON_EXISTENT", default="default_value")
    print(f"   NON_EXISTENT: {value}\n")

    # 6. Cleaning up
    print("6. Cleaning up environment variables:")
    result = unset_env_var("API_URL")
    print(f"   Unset API_URL: {result}")
    result = unset_env_var("PORT")
    print(f"   Unset PORT: {result}")
    result = unset_env_var("NON_EXISTENT")
    print(f"   Unset NON_EXISTENT: {result}")


if __name__ == "__main__":
    main()
