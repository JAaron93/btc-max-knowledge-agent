import os

import pytest

from env_tools import get_env_var, set_env_var, unset_env_var


# Fixture to manage environment variables for tests
@pytest.fixture(autouse=True)
def manage_env_vars():
    original_environ = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(original_environ)


# Tests for set_env_var
def test_set_new_variable():
    assert set_env_var("NEW_VAR", "test_value") is True
    assert os.environ.get("NEW_VAR") == "test_value"


def test_set_existing_variable_no_override():
    os.environ["EXISTING_VAR"] = "initial_value"
    assert set_env_var("EXISTING_VAR", "new_value", allow_override=False) is False
    assert os.environ.get("EXISTING_VAR") == "initial_value"


def test_set_existing_variable_with_override():
    os.environ["EXISTING_VAR"] = "initial_value"
    assert set_env_var("EXISTING_VAR", "new_value", allow_override=True) is True
    assert os.environ.get("EXISTING_VAR") == "new_value"


def test_set_variable_with_non_string_value():
    assert set_env_var("INT_VAR", 123) is True
    assert os.environ.get("INT_VAR") == "123"


def test_set_invalid_key_type():
    with pytest.raises(TypeError):
        set_env_var(123, "value")


def test_set_empty_key():
    with pytest.raises(ValueError):
        set_env_var("", "value")


# Tests for get_env_var
def test_get_existing_variable():
    os.environ["MY_VAR"] = "hello"
    assert get_env_var("MY_VAR") == "hello"


def test_get_non_existent_variable_with_default():
    assert get_env_var("NON_EXISTENT_VAR", "default_val") == "default_val"


def test_get_non_existent_variable_no_default():
    assert get_env_var("NON_EXISTENT_VAR") is None


def test_get_invalid_key_type():
    with pytest.raises(TypeError):
        get_env_var(123)


# Tests for unset_env_var
def test_unset_existing_variable():
    os.environ["TO_DELETE"] = "some_value"
    assert unset_env_var("TO_DELETE") is True
    assert "TO_DELETE" not in os.environ


def test_unset_non_existent_variable():
    assert unset_env_var("NON_EXISTENT_VAR") is False


def test_unset_invalid_key_type():
    with pytest.raises(TypeError):
        unset_env_var(123)


# Tests for logging behavior
def test_set_env_var_logs_info_for_new_variable(caplog):
    """Test that setting a new environment variable logs an info message."""
    import logging

    caplog.set_level(logging.INFO)

    set_env_var("LOG_TEST_VAR", "test_value")

    assert "Set environment variable 'LOG_TEST_VAR' = 'test_value'" in caplog.text


def test_set_env_var_logs_warning_for_existing_variable_no_override(caplog):
    """Test that attempting to override without permission logs a warning."""
    import logging

    caplog.set_level(logging.WARNING)

    os.environ["EXISTING_VAR"] = "original_value"
    set_env_var("EXISTING_VAR", "new_value", allow_override=False)

    assert "Environment variable 'EXISTING_VAR' already exists" in caplog.text
    assert "Skipping assignment" in caplog.text
    assert "Use allow_override=True to override" in caplog.text


def test_set_env_var_logs_warning_for_override(caplog):
    """Test that overriding an existing variable logs a warning."""
    import logging

    caplog.set_level(logging.WARNING)

    os.environ["EXISTING_VAR"] = "original_value"
    set_env_var("EXISTING_VAR", "new_value", allow_override=True)

    assert "Overriding environment variable 'EXISTING_VAR'" in caplog.text
    assert "from 'original_value' to 'new_value'" in caplog.text


def test_unset_env_var_logs_info_for_existing_variable(caplog):
    """Test that unsetting an existing variable logs an info message."""
    import logging

    caplog.set_level(logging.INFO)

    os.environ["TO_UNSET"] = "some_value"
    unset_env_var("TO_UNSET")

    assert "Removed environment variable 'TO_UNSET'" in caplog.text


def test_unset_env_var_no_log_for_non_existent_variable(caplog):
    """Test that unsetting a non-existent variable doesn't log anything."""
    import logging

    caplog.set_level(logging.INFO)

    unset_env_var("NON_EXISTENT")

    assert "Removed environment variable 'NON_EXISTENT'" not in caplog.text
