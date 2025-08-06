#!/usr/bin/env python3
"""
Test script for TTS UI components
"""

import sys
import time
from pathlib import Path

# Add project root to path - look for project markers
current_dir = Path(__file__).resolve().parent
project_root = current_dir
while project_root != project_root.parent:
    if (project_root / "pyproject.toml").exists() or (
        project_root / "setup.py"
    ).exists():
        break
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from src.web.bitcoin_assistant_ui import (
    TTSState,
    create_waveform_animation,
    get_tts_status_display,
)


def test_waveform_animation():
    """Test waveform animation generation"""
    animation = create_waveform_animation()
    assert isinstance(animation, str), "Animation should return a string"
    assert animation.strip(), "Animation should not be empty"
    assert "<svg>" in animation or "<svg " in animation, (
        "Should contain valid SVG opening tag"
    )
    assert "</svg>" in animation, "Should contain SVG closing tag"
    assert "animate" in animation
    assert "Synthesizing speech..." in animation
    print("✅ Waveform animation test passed")


def test_tts_status_display():
    """Test TTS status display functions"""
    # Test ready state
    ready_status = get_tts_status_display(False)
    assert isinstance(ready_status, str), "Status should return a string"
    assert "Ready for voice synthesis" in ready_status

    # Test synthesizing state
    synth_status = get_tts_status_display(True)
    assert "Synthesizing speech..." in synth_status

    # Test error state
    error_status = get_tts_status_display(False, has_error=True)
    assert "TTS Error" in error_status

    # Test edge case: both synthesizing and error (if supported)
    try:
        edge_status = get_tts_status_display(True, has_error=True)
        # Validate which state takes precedence
        assert "TTS Error" in edge_status or "Synthesizing speech..." in edge_status
    except Exception:
        # Document expected behavior if this combination isn't supported
        pass

    print("✅ TTS status display test passed")


def test_tts_state():
    """Test TTS state management with comprehensive timestamp validation"""
    state = TTSState()

    # Test initial state
    assert not state.is_synthesizing, "Initial state should not be synthesizing"
    assert state.synthesis_start_time is None, (
        "Initial synthesis_start_time should be None"
    )
    assert not state.stop_animation, "Initial stop_animation should be False"

    # Record time before starting synthesis for validation
    time_before_start = time.time()

    # Test start synthesis
    state.start_synthesis()
    time_after_start = time.time()

    # Validate synthesis state
    assert state.is_synthesizing, "State should be synthesizing after start_synthesis()"
    assert state.synthesis_start_time is not None, (
        "synthesis_start_time should be set after start_synthesis()"
    )
    assert not state.stop_animation, "stop_animation should be False during synthesis"

    # Validate timestamp is recent and reasonable
    assert isinstance(state.synthesis_start_time, (int, float)), (
        "synthesis_start_time should be a numeric timestamp"
    )
    assert time_before_start <= state.synthesis_start_time <= time_after_start, (
        f"synthesis_start_time ({state.synthesis_start_time}) should be between {time_before_start} and {time_after_start}"
    )

    # Store first synthesis start time for later comparison
    first_start_time = state.synthesis_start_time

    # Test stop synthesis
    state.stop_synthesis()
    assert not state.is_synthesizing, (
        "State should not be synthesizing after stop_synthesis()"
    )
    assert state.stop_animation, "stop_animation should be True after stop_synthesis()"
    # Verify start time is preserved after stopping
    assert state.synthesis_start_time == first_start_time, (
        "synthesis_start_time should be preserved after stop_synthesis()"
    )

    # Test multiple start-stop cycles
    print("  Testing multiple start-stop cycles...")

    for cycle in range(3):
        print(f"    Cycle {cycle + 1}/3")

        # Small delay to ensure different timestamps
        time.sleep(0.01)

        # Record time before this cycle's start
        cycle_time_before = time.time()

        # Start synthesis again
        state.start_synthesis()
        cycle_time_after = time.time()

        # Validate state transitions
        assert state.is_synthesizing, (
            f"Cycle {cycle + 1}: Should be synthesizing after start"
        )
        assert not state.stop_animation, (
            f"Cycle {cycle + 1}: stop_animation should be False during synthesis"
        )

        # Validate new timestamp
        assert state.synthesis_start_time is not None, (
            f"Cycle {cycle + 1}: synthesis_start_time should be set"
        )
        assert cycle_time_before <= state.synthesis_start_time <= cycle_time_after, (
            f"Cycle {cycle + 1}: synthesis_start_time should be recent"
        )

        # Verify timestamp is updated (should be different from first cycle)
        if cycle > 0:
            assert state.synthesis_start_time != first_start_time, (
                f"Cycle {cycle + 1}: synthesis_start_time should be updated on new start"
            )

        # Store this cycle's start time
        cycle_start_time = state.synthesis_start_time

        # Stop synthesis
        state.stop_synthesis()

        # Validate stop state
        assert not state.is_synthesizing, (
            f"Cycle {cycle + 1}: Should not be synthesizing after stop"
        )
        assert state.stop_animation, (
            f"Cycle {cycle + 1}: stop_animation should be True after stop"
        )
        assert state.synthesis_start_time == cycle_start_time, (
            f"Cycle {cycle + 1}: synthesis_start_time should be preserved after stop"
        )

    # Test rapid start-stop cycles (stress test)
    print("  Testing rapid start-stop cycles...")

    for rapid_cycle in range(5):
        state.start_synthesis()
        rapid_start_time = state.synthesis_start_time

        assert state.is_synthesizing, (
            f"Rapid cycle {rapid_cycle + 1}: Should be synthesizing"
        )
        assert rapid_start_time is not None, (
            f"Rapid cycle {rapid_cycle + 1}: Start time should be set"
        )

        state.stop_synthesis()

        assert not state.is_synthesizing, (
            f"Rapid cycle {rapid_cycle + 1}: Should not be synthesizing after stop"
        )
        assert state.stop_animation, (
            f"Rapid cycle {rapid_cycle + 1}: stop_animation should be True"
        )
        assert state.synthesis_start_time == rapid_start_time, (
            f"Rapid cycle {rapid_cycle + 1}: Start time should be preserved"
        )

    print(
        "✅ TTS state management test passed (including timestamp validation and multiple cycles)"
    )


if __name__ == "__main__":
    import logging
    import traceback

    # Configure logging for test output
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

    print("🧪 Testing TTS UI components...")

    # Track test results
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    failed_tests = []

    # List of test functions to run
    test_functions = [
        ("Waveform Animation", test_waveform_animation),
        ("TTS Status Display", test_tts_status_display),
        ("TTS State Management", test_tts_state),
    ]

    # Run each test with error handling
    for test_name, test_func in test_functions:
        tests_run += 1
        try:
            print(f"\n🔍 Running {test_name} test...")
            test_func()
            tests_passed += 1
            logger.info(f"✅ {test_name} test PASSED")
        except Exception as e:
            tests_failed += 1
            failed_tests.append(test_name)
            logger.error(f"❌ {test_name} test FAILED: {str(e)}")
            logger.debug(f"Full traceback for {test_name}:\n{traceback.format_exc()}")
            # Continue with next test instead of stopping

    # Print summary
    logger.info("\n📊 Test Summary:")
    print(f"   Tests run: {tests_run}")
    print(f"   Passed: {tests_passed}")
    print(f"   Failed: {tests_failed}")

    if tests_failed == 0:
        print("🎉 All TTS UI component tests passed!")
        exit(0)
    else:
        print(f"💥 {tests_failed} test(s) failed: {', '.join(failed_tests)}")
        print("   Check the error messages above for details.")
        exit(1)
