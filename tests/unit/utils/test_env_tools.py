"""Unit tests for the env_tools module."""

import logging
import os
import unittest
from unittest.mock import MagicMock, patch

from env_tools import get_env_var, set_env_var, unset_env_var

# Configure logging for tests
logging.basicConfig(level=logging.INFO)


class TestEnvTools(unittest.TestCase):
    """Test suite for environment variable helpers."""

    def setUp(self) -> None:
        """Set up test environment before each test."""
        self.initial_environ = os.environ.copy()
        self.test_key = "TEST_VARIABLE"
        self.test_value = "test_value"
        self.override_value = "new_value"

        # Clean up environment variable if it exists
        if self.test_key in os.environ:
            del os.environ[self.test_key]

    def tearDown(self) -> None:
        """Clean up test environment after each test."""
        os.environ.clear()
        os.environ.update(self.initial_environ)

    @patch("env_tools.logger")
    def test_set_when_absent(self, mock_logger: MagicMock) -> None:
        """Test setting a variable that does not exist."""
        result = set_env_var(self.test_key, self.test_value)
        self.assertTrue(result)
        self.assertEqual(os.environ.get(self.test_key), self.test_value)
        mock_logger.info.assert_called_with(
            f"Set environment variable '{self.test_key}' = '{self.test_value}'"
        )
        self.assertFalse(mock_logger.warning.called)

    @patch("env_tools.logger")
    def test_skip_when_present(self, mock_logger: MagicMock) -> None:
        """Test skipping a variable that already exists."""
        os.environ[self.test_key] = self.test_value
        result = set_env_var(self.test_key, self.override_value)
        self.assertFalse(result)
        self.assertEqual(os.environ.get(self.test_key), self.test_value)
        mock_logger.warning.assert_called_with(
            f"Environment variable '{self.test_key}' already exists with value '{self.test_value}'. "
            f"Skipping assignment of '{self.override_value}'. Use allow_override=True to override."
        )
        self.assertFalse(mock_logger.info.called)

    @patch("env_tools.logger")
    def test_override_when_present(self, mock_logger: MagicMock) -> None:
        """Test overriding a variable when allow_override is True."""
        os.environ[self.test_key] = self.test_value
        result = set_env_var(self.test_key, self.override_value, allow_override=True)
        self.assertTrue(result)
        self.assertEqual(os.environ.get(self.test_key), self.override_value)
        mock_logger.warning.assert_called_with(
            f"Overriding environment variable '{self.test_key}' from '{self.test_value}' to '{self.override_value}'"
        )
        mock_logger.info.assert_called_with(
            f"Set environment variable '{self.test_key}' = '{self.override_value}'"
        )

    def test_invalid_key_type(self) -> None:
        """Test that a non-string key raises TypeError."""
        with self.assertRaises(TypeError):
            set_env_var(123, self.test_value)  # type: ignore

    def test_empty_key(self) -> None:
        """Test that an empty key raises ValueError."""
        with self.assertRaises(ValueError):
            set_env_var("", self.test_value)

    def test_get_existing_var(self) -> None:
        """Test getting an existing environment variable."""
        os.environ[self.test_key] = self.test_value
        self.assertEqual(get_env_var(self.test_key), self.test_value)

    def test_get_nonexistent_var(self) -> None:
        """Test getting a non-existent variable returns None."""
        self.assertIsNone(get_env_var("NON_EXISTENT_VAR"))

    def test_get_with_default(self) -> None:
        """Test getting a non-existent variable with a default value."""
        default_val = "default"
        self.assertEqual(
            get_env_var("NON_EXISTENT_VAR", default=default_val), default_val
        )

    def test_unset_existing_var(self) -> None:
        """Test unsetting an existing environment variable."""
        os.environ[self.test_key] = self.test_value
        self.assertTrue(unset_env_var(self.test_key))
        self.assertNotIn(self.test_key, os.environ)

    def test_unset_nonexistent_var(self) -> None:
        """Test unsetting a non-existent variable returns False."""
        self.assertFalse(unset_env_var("NON_EXISTENT_VAR"))

    def test_value_type_conversion(self) -> None:
        """Test that different value types are converted to strings."""
        # Test integer
        set_env_var("INT_VAR", 42)
        self.assertEqual(os.environ.get("INT_VAR"), "42")

        # Test float
        set_env_var("FLOAT_VAR", 3.14)
        self.assertEqual(os.environ.get("FLOAT_VAR"), "3.14")

        # Test boolean
        set_env_var("BOOL_VAR", True)
        self.assertEqual(os.environ.get("BOOL_VAR"), "True")

    def test_whitespace_key_validation(self) -> None:
        """Test that whitespace-only keys are rejected."""
        with self.assertRaises(ValueError):
            set_env_var("   ", "value")

        with self.assertRaises(ValueError):
            set_env_var("\t\n", "value")

    def test_key_validation_for_get_env_var(self) -> None:
        """Test key validation for get_env_var function."""
        with self.assertRaises(TypeError):
            get_env_var(123)  # type: ignore

        with self.assertRaises(ValueError):
            get_env_var("")

        with self.assertRaises(ValueError):
            get_env_var("   ")

    def test_key_validation_for_unset_env_var(self) -> None:
        """Test key validation for unset_env_var function."""
        with self.assertRaises(TypeError):
            unset_env_var(123)  # type: ignore

        with self.assertRaises(ValueError):
            unset_env_var("")

        with self.assertRaises(ValueError):
            unset_env_var("   ")

    @patch("env_tools.logger")
    def test_no_silent_overrides(self, mock_logger: MagicMock) -> None:
        """Test that overrides are never silent - they always log warnings."""
        # Set initial value
        os.environ[self.test_key] = self.test_value

        # Attempt override without permission
        result1 = set_env_var(self.test_key, self.override_value)
        self.assertFalse(result1)
        mock_logger.warning.assert_called_with(
            f"Environment variable '{self.test_key}' already exists with value '{self.test_value}'. "
            f"Skipping assignment of '{self.override_value}'. Use allow_override=True to override."
        )

        # Reset mock
        mock_logger.reset_mock()

        # Attempt override with permission
        result2 = set_env_var(self.test_key, self.override_value, allow_override=True)
        self.assertTrue(result2)
        mock_logger.warning.assert_called_with(
            f"Overriding environment variable '{self.test_key}' from '{self.test_value}' to '{self.override_value}'"
        )

        # Verify warning was called in both cases
        self.assertEqual(mock_logger.warning.call_count, 1)

    @patch("env_tools.logger")
    def test_logging_unset_operation(self, mock_logger: MagicMock) -> None:
        """Test that unset operations are properly logged."""
        os.environ[self.test_key] = self.test_value
        result = unset_env_var(self.test_key)
        self.assertTrue(result)
        mock_logger.info.assert_called_with(
            f"Removed environment variable '{self.test_key}'"
        )


if __name__ == "__main__":
    unittest.main()
