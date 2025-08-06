import logging

import pytest

from src.security.models import (
    DEFAULT_THRESHOLD_HIGH,
    DEFAULT_THRESHOLD_LOW,
    SecurityEventType,
    SecuritySeverity,
    _sanitize_thresholds,
    get_contextual_severity_for_event_type,
)


# Test cases for the _sanitize_thresholds helper function
@pytest.mark.parametrize(
    "low, high, expected_low, expected_high, expected_log",
    [
        # 1. Valid numeric input (no change)
        (10, 100, 10.0, 100.0, []),
        (0.5, 1.5, 0.5, 1.5, []),
        # 2. Non-numeric / negative values -> defaults used
        ("invalid", 100, DEFAULT_THRESHOLD_LOW, 100.0, ["Invalid threshold_low value"]),
        (10, "invalid", 10.0, DEFAULT_THRESHOLD_HIGH, ["Invalid threshold_high value"]),
        (-5, 100, DEFAULT_THRESHOLD_LOW, 100.0, ["Invalid threshold_low value"]),
        (10, -100, 10.0, DEFAULT_THRESHOLD_HIGH, ["Invalid threshold_high value"]),
        (None, 100, DEFAULT_THRESHOLD_LOW, 100.0, ["Invalid threshold_low value"]),
        # 3. low >= high -> defaults restored
        (
            100,
            10,
            DEFAULT_THRESHOLD_LOW,
            DEFAULT_THRESHOLD_HIGH,
            ["Invalid threshold relationship"],
        ),
        (
            100,
            100,
            DEFAULT_THRESHOLD_LOW,
            DEFAULT_THRESHOLD_HIGH,
            ["Invalid threshold relationship"],
        ),
        # 4. Mix of invalid type and relationship
        (
            "invalid",
            "invalid",
            DEFAULT_THRESHOLD_LOW,
            DEFAULT_THRESHOLD_HIGH,
            ["Invalid threshold_high value", "Invalid threshold_low value"],
        ),
    ],
)
def test_sanitize_thresholds(
    low, high, expected_low, expected_high, expected_log, caplog
):
    """Tests the _sanitize_thresholds helper with various inputs."""
    with caplog.at_level(logging.WARNING):
        sanitized_low, sanitized_high = _sanitize_thresholds(low, high)
        assert sanitized_low == expected_low
        assert sanitized_high == expected_high

        # 4. Preservation of logging (use caplog to assert warning messages)
        for log_msg in expected_log:
            assert any(log_msg in record.message for record in caplog.records)


# Tests for the refactored get_contextual_severity_for_event_type function
def test_severity_with_valid_thresholds(caplog):
    """Ensures no warnings are logged with valid custom thresholds."""
    with caplog.at_level(logging.WARNING):
        get_contextual_severity_for_event_type(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            {"threshold_low": 20, "threshold_high": 80, "attempt_count": 50},
        )
        assert not caplog.records


def test_severity_with_invalid_thresholds(caplog):
    """Verifies that invalid thresholds trigger warnings and defaults are used."""
    with caplog.at_level(logging.WARNING):
        # Non-numeric high threshold
        severity = get_contextual_severity_for_event_type(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            {"threshold_low": 20, "threshold_high": "invalid", "attempt_count": 60},
        )
        assert any("Invalid threshold_high" in r.message for r in caplog.records)
        # Should use default high (50), making 60 an ERROR
        assert severity == SecuritySeverity.ERROR

    caplog.clear()

    with caplog.at_level(logging.WARNING):
        # low >= high, resetting to defaults
        get_contextual_severity_for_event_type(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            {"threshold_low": 100, "threshold_high": 20, "attempt_count": 30},
        )
        assert any(
            "Invalid threshold relationship" in r.message for r in caplog.records
        )
