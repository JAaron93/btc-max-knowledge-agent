#!/usr/bin/env python3
"""
Test script for audio streaming functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.audio_utils import (
    AudioProcessingError,
    create_gradio_streaming_audio,
    get_audio_streaming_manager,
    prepare_audio_for_streaming,
)

# Audio validation constants
MIN_AUDIO_DATA_SIZE = 8  # Minimum bytes required for valid audio data


def test_streaming_manager():
    """Test the AudioStreamingManager functionality."""
    print("🧪 Testing AudioStreamingManager...")

    manager = get_audio_streaming_manager()

    # Test initial state
    status = manager.get_stream_status()
    print(f"Initial status: {status}")
    assert not status["is_streaming"]
    assert not status["has_current_stream"]

    # Test with mock audio data
    mock_audio = b"mock_audio_data_for_testing" * 100  # Create some mock audio data

    try:
        # Test streaming data preparation
        streaming_data = manager.prepare_streaming_audio(mock_audio, is_cached=False)
        print(f"Streaming data prepared: {streaming_data.keys()}")

        assert "audio_bytes" in streaming_data
        assert "duration" in streaming_data
        assert "is_cached" in streaming_data
        assert "gradio_audio" in streaming_data
        assert "gradio_tuple" in streaming_data
        assert streaming_data["is_cached"] == False

        # Test cached audio preparation
        cached_data = manager.create_instant_replay_data(mock_audio)
        print(f"Cached data prepared: {cached_data.keys()}")

        assert cached_data["is_cached"] == True
        assert cached_data["instant_replay"] == True
        assert cached_data["synthesis_time"] == 0.0

        # Test synthesized audio preparation
        synth_data = manager.create_synthesized_audio_data(
            mock_audio, synthesis_time=1.5
        )
        print(f"Synthesized data prepared: {synth_data.keys()}")

        assert synth_data["is_cached"] == False
        assert synth_data["instant_replay"] == False
        assert synth_data["synthesis_time"] == 1.5

        print("✅ AudioStreamingManager tests passed!")
        return True

    except Exception as e:
        print(f"❌ AudioStreamingManager test failed: {e}")
        return False


def test_convenience_functions():
    """Test convenience functions for streaming."""
    print("\n🧪 Testing convenience functions...")

    mock_audio = b"mock_audio_data_for_testing" * 50

    try:
        # Test prepare_audio_for_streaming
        streaming_data = prepare_audio_for_streaming(mock_audio, is_cached=True)
        print(f"Convenience streaming data: {streaming_data.keys()}")

        assert "gradio_tuple" in streaming_data
        assert streaming_data["is_cached"] == True

        # Test create_gradio_streaming_audio
        gradio_tuple = create_gradio_streaming_audio(mock_audio, is_cached=False)
        print(
            f"Gradio tuple: {type(gradio_tuple)}, length: {len(gradio_tuple) if isinstance(gradio_tuple, tuple) else 'not tuple'}"
        )

        assert isinstance(gradio_tuple, tuple)
        assert len(gradio_tuple) == 2  # (sample_rate, audio_data)

        print("✅ Convenience functions tests passed!")
        return True

    except Exception as e:
        print(f"❌ Convenience functions test failed: {e}")
        return False


async def test_tts_integration():
    """Test TTS service integration with streaming."""
    print("\n🧪 Testing TTS integration with streaming...")

    # Import TTS service only when needed to avoid heavy initialization
    from utils.tts_service import get_tts_service

    tts_service = get_tts_service()

    if not tts_service.is_enabled():
        print(
            "⚠️  TTS service not enabled (missing API key), skipping TTS integration test"
        )
        return True

    try:
        streaming_manager = get_audio_streaming_manager()

        # Test text synthesis
        test_text = "This is a test of the audio streaming functionality."

        print(f"Synthesizing: '{test_text}'")
        audio_bytes = await tts_service.synthesize_text(test_text)

        print(f"Synthesized {len(audio_bytes)} bytes of audio")

        # Test streaming preparation
        streaming_data = streaming_manager.create_synthesized_audio_data(
            audio_bytes, synthesis_time=2.0
        )

        assert "gradio_tuple" in streaming_data
        assert streaming_data["synthesis_time"] == 2.0
        assert not streaming_data["instant_replay"]

        # Test cached replay
        cached_audio = tts_service.get_cached_audio(test_text)
        if cached_audio:
            replay_data = streaming_manager.create_instant_replay_data(cached_audio)
            assert replay_data["instant_replay"] == True
            assert replay_data["synthesis_time"] == 0.0
            print("✅ Cached replay data created successfully")

        print("✅ TTS integration tests passed!")
        return True

    except Exception as e:
        print(f"❌ TTS integration test failed: {e}")
        return False


def test_error_handling():
    """Test error handling in streaming components."""
    print("\n🧪 Testing error handling...")

    manager = get_audio_streaming_manager()

    try:
        # Test with invalid audio data
        try:
            manager.prepare_streaming_audio(b"", is_cached=False)
            print("❌ Should have failed with empty audio data")
            return False
        except AudioProcessingError:
            print("✅ Correctly handled empty audio data")

        # Test with audio data below minimum size threshold
        # Use data that is exactly 1 byte below the minimum required size
        below_threshold_data = b"x" * (MIN_AUDIO_DATA_SIZE - 1)
        try:
            manager.prepare_streaming_audio(below_threshold_data, is_cached=False)
            print(
                f"❌ Should have failed with {len(below_threshold_data)}-byte audio data (below {MIN_AUDIO_DATA_SIZE}-byte minimum)"
            )
            return False
        except AudioProcessingError:
            print(
                f"✅ Correctly handled {len(below_threshold_data)}-byte audio data (below {MIN_AUDIO_DATA_SIZE}-byte minimum)"
            )

        print("✅ Error handling tests passed!")
        return True

    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


async def main():
    """Run all streaming tests."""
    print("🚀 Starting audio streaming functionality tests...\n")

    tests = [
        ("Streaming Manager", test_streaming_manager),
        ("Convenience Functions", test_convenience_functions),
        ("TTS Integration", test_tts_integration),
        ("Error Handling", test_error_handling),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{'=' * 50}")
        print(f"Running: {test_name}")
        print("=" * 50)

        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()

        results.append((test_name, result))

    # Summary
    print(f"\n{'=' * 50}")
    print("TEST SUMMARY")
    print("=" * 50)

    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("🎉 All streaming functionality tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
