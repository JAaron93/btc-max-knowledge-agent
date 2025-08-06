#!/usr/bin/env python3
"""
Simple test for TTS performance optimizations.
"""

import sys
from pathlib import Path


def find_project_root(start_path: Path = None) -> Path:
    """
    Find the project root by traversing parent directories looking for project markers.

    Args:
        start_path: Starting path for search (defaults to current file's directory)

    Returns:
        Path to project root

    Raises:
        RuntimeError: If project root cannot be found
    """
    if start_path is None:
        start_path = Path(__file__).parent

    # Project markers to look for (in order of preference)
    project_markers = [
        ".git",  # Git repository
        "setup.py",  # Python setup file
        "pyproject.toml",  # Modern Python project file
        "requirements.txt",  # Python dependencies
        "src",  # Source directory (common in this project)
        ".kiro",  # Kiro AI assistant directory (specific to this project)
    ]

    current_path = start_path.resolve()

    # Traverse up the directory tree
    while current_path != current_path.parent:  # Stop at filesystem root
        # Check if any project markers exist in current directory
        for marker in project_markers:
            marker_path = current_path / marker
            if marker_path.exists():
                return current_path

        # Move up one directory
        current_path = current_path.parent

    # If we reach here, no project root was found
    raise RuntimeError(
        f"Could not find project root. Searched from {start_path} up to filesystem root. "
        f"Looking for markers: {', '.join(project_markers)}"
    )


# Add project root to path
try:
    project_root = find_project_root()
    sys.path.insert(0, str(project_root))
except RuntimeError as e:
    print(f"Error finding project root: {e}")
    # Fallback to the old method as last resort
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    print(f"Using fallback project root: {project_root}")


def test_buffer_optimization():
    """Test optimized buffer sizes."""
    print("Testing buffer size optimization...")

    try:
        from src.utils.audio_utils import get_optimal_buffer_size

        # Test different scenarios
        # Test case parameters: (audio_size_bytes, is_cached, connection_type)
        test_cases = [
            (1024, False, "default"),  # 1KB - Small file, not cached
            (1024, True, "default"),  # 1KB - Small file, cached
            (1024 * 1024, False, "default"),  # 1MB - Large file, not cached
            (32768, False, "low_latency"),  # 32KB - Medium file, low latency
            (
                1024 * 1024,
                False,
                "high_throughput",
            ),  # 1MB - Large file, high throughput
        ]
        for audio_size, is_cached, connection_type in test_cases:
            buffer_size = get_optimal_buffer_size(
                audio_size, is_cached, connection_type
            )

            # Validate buffer size is reasonable
            if buffer_size <= 0:
                raise ValueError(f"Invalid buffer size: {buffer_size}")
            if (
                buffer_size > audio_size * 2
            ):  # Buffer shouldn't be more than 2x audio size
                print(
                    f"⚠️  Warning: Buffer size ({buffer_size}) seems large for audio size ({audio_size})"
                )

            print(
                f"Audio size: {audio_size:,} bytes, cached: {is_cached}, "
                f"connection: {connection_type} -> buffer: {buffer_size:,} bytes"
            )

        print("✅ Buffer optimization test completed")
        return True

    except Exception as e:
        print(f"❌ Buffer optimization test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_imports():
    """Test that all imports work correctly and components are functional."""
    print("Testing imports and functionality...")

    try:
        # Test audio utils imports and functionality
        from src.utils.audio_utils import (
            STREAMING_BUFFER_SIZES,
            AudioFormatConverter,
            AudioStreamProcessor,
            get_optimal_buffer_size,
        )

        print("✅ Audio utils imports successful")

        # Test get_optimal_buffer_size function
        buffer_size = get_optimal_buffer_size(1024, False, "default")
        assert isinstance(buffer_size, int), f"Expected int, got {type(buffer_size)}"
        assert buffer_size > 0, f"Buffer size should be positive, got {buffer_size}"
        print(f"  ✓ get_optimal_buffer_size() functional (returned {buffer_size})")

        # Test STREAMING_BUFFER_SIZES constant
        assert isinstance(
            STREAMING_BUFFER_SIZES, dict
        ), f"Expected dict, got {type(STREAMING_BUFFER_SIZES)}"
        assert (
            len(STREAMING_BUFFER_SIZES) > 0
        ), "STREAMING_BUFFER_SIZES should not be empty"
        print(
            f"  ✓ STREAMING_BUFFER_SIZES accessible ({len(STREAMING_BUFFER_SIZES)} entries)"
        )

        # Test AudioFormatConverter class instantiation
        converter = AudioFormatConverter()
        assert hasattr(
            converter, "convert"
        ), "AudioFormatConverter should have convert method"
        print("  ✓ AudioFormatConverter instantiable")

        # Test AudioStreamProcessor class instantiation
        processor = AudioStreamProcessor()
        assert hasattr(
            processor, "process_chunk"
        ), "AudioStreamProcessor should have process_chunk method"
        print("  ✓ AudioStreamProcessor instantiable")

        # Test TTS service imports and functionality
        from src.utils.tts_service import TTSConfig, TTSService

        print("✅ TTS service imports successful")

        # Test TTSConfig class instantiation
        config = TTSConfig()
        assert hasattr(config, "api_key"), "TTSConfig should have api_key attribute"
        assert hasattr(config, "voice_id"), "TTSConfig should have voice_id attribute"
        print("  ✓ TTSConfig instantiable")

        # Test TTSService class instantiation (without actual API calls)
        # Note: We don't initialize with real config to avoid API calls in tests
        assert callable(TTSService), "TTSService should be callable (class)"
        print("  ✓ TTSService class accessible")

        print("✅ All imports and basic functionality verified")
        return True

    except Exception as e:
        print(f"❌ Import/functionality test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run simple optimization tests."""
    print("🚀 Starting Simple TTS Performance Tests")
    print("=" * 40)

    success = True

    # Test imports first
    if not test_imports():
        success = False

    print()

    # Test buffer optimization
    if not test_buffer_optimization():
        success = False

    print()

    if success:
        print("✅ All simple tests completed successfully!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
