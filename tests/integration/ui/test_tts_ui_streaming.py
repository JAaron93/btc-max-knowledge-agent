#!/usr/bin/env python3
"""
Test TTS UI streaming components.
"""

import sys
from pathlib import Path

# Add project root to path (avoid duplicates)
# Add project root to path (avoid duplicates)
project_root = Path(
    __file__
).parent.parent.parent.parent  # Go up from tests/integration/ui/ to project root
project_root_str = str(project_root)
src_path_str = str(project_root / "src")

if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
if src_path_str not in sys.path:
    sys.path.insert(0, src_path_str)


def test_ui_streaming_functions():
    """Test UI streaming functions."""
    print("🧪 Testing UI streaming functions...")

    try:
        # Import UI functions
        from web.bitcoin_assistant_ui import (
            create_waveform_animation,
            get_tts_status_display,
            query_bitcoin_assistant_with_streaming,
        )

        # Test status display functions
        ready_status = get_tts_status_display(False)
        print(f"✅ Ready status HTML generated: {len(ready_status)} chars")

        synth_status = get_tts_status_display(True)
        print(f"✅ Synthesis status HTML generated: {len(synth_status)} chars")

        error_status = get_tts_status_display(False, has_error=True)
        print(f"✅ Error status HTML generated: {len(error_status)} chars")

        # Test waveform animation
        waveform = create_waveform_animation()
        print(f"✅ Waveform animation generated: {len(waveform)} chars")

        # Verify HTML content
        assert "svg" in waveform.lower()
        assert "animate" in waveform.lower()
        assert "synthesizing" in waveform.lower()

        print("✅ UI streaming functions tests passed!")
        return True

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ UI streaming functions test failed: {e}")
        return False


def test_streaming_query_function():
    """Test the streaming query function (without actual API call)."""
    print("\n🧪 Testing streaming query function...")

    try:
        from web.bitcoin_assistant_ui import query_bitcoin_assistant_with_streaming

        # Test with empty question
        answer, sources, audio, streaming_info = query_bitcoin_assistant_with_streaming(
            "", False, 0.7
        )

        assert "Please enter a question" in answer
        assert sources == ""
        assert audio is None
        assert streaming_info is None

        print("✅ Empty question handling works")

        # Note: We can't test actual API calls without the server running
        # But we can verify the function signature and basic validation

        print("✅ Streaming query function tests passed!")
        return True

    except Exception as e:
        print(f"❌ Streaming query function test failed: {e}")
        return False


def test_tts_state_management():
    """Test TTS state management."""
    print("\n🧪 Testing TTS state management...")

    try:
        from web.bitcoin_assistant_ui import TTSState

        # Create TTS state
        state = TTSState()

        # Test initial state
        assert not state.is_synthesizing
        assert state.synthesis_start_time is None
        assert not state.stop_animation

        # Test start synthesis
        state.start_synthesis()
        assert state.is_synthesizing
        assert state.synthesis_start_time is not None
        assert not state.stop_animation

        # Test stop synthesis
        state.stop_synthesis()
        assert not state.is_synthesizing
        assert state.stop_animation
        # Verify synthesis_start_time behavior after stopping
        # (This depends on the actual implementation - may be None or preserved)
        print(f"   synthesis_start_time after stop: {state.synthesis_start_time}")

        print("✅ TTS state management works correctly")
        return True

    except Exception as e:
        print(f"❌ TTS state management test failed: {e}")
        return False


def test_gradio_interface_creation():
    """Test Gradio interface creation (without launching)."""
    print("\n🧪 Testing Gradio interface creation...")

    try:
        from web.bitcoin_assistant_ui import create_bitcoin_assistant_ui

        # Create interface (but don't launch)
        interface = create_bitcoin_assistant_ui()

        # Basic checks
        assert interface is not None
        print("✅ Gradio interface created successfully")

        # Check if interface has the expected components
        # Note: This is a basic check - full UI testing would require more complex setup

        return True

    except ImportError as e:
        # Explicitly indicate the test was skipped due to missing dependency
        print(f"⚠️  Gradio not available for testing (skipped): {e}")
        return None
    except Exception as e:
        print(f"❌ Gradio interface creation test failed: {e}")
        return False


def main():
    """Run all UI streaming tests."""
    print("🚀 Starting TTS UI streaming tests...\n")

    tests = [
        ("UI Streaming Functions", test_ui_streaming_functions),
        ("Streaming Query Function", test_streaming_query_function),
        ("TTS State Management", test_tts_state_management),
        ("Gradio Interface Creation", test_gradio_interface_creation),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{'=' * 50}")
        print(f"Running: {test_name}")
        print("=" * 50)

        result = test_func()
        results.append((test_name, result))

    # Summary
    print(f"\n{'=' * 50}")
    print("UI STREAMING TEST SUMMARY")
    print("=" * 50)

    passed = 0
    for test_name, result in results:
        passed = 0
        for test_name, result in results:
            if result is None:
                status = "⏭️ SKIPPED"
            else:
                status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name}: {status}")
            if result is True:  # Explicitly check for True to avoid counting None
                passed += 1

    # Count skipped for clarity
    skipped = sum(1 for _, r in results if r is None)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed, {skipped} skipped")

    if passed == total - skipped and skipped > 0:
        print(
            "ℹ️  All executed tests passed; some tests were skipped due to missing dependencies."
        )
        return True
    elif passed == total:
        print("🎉 All TTS UI streaming tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
