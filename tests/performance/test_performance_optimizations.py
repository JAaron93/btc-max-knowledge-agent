#!/usr/bin/env python3
"""
Test script for TTS performance optimizations.
"""

import asyncio
import os
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
    # Fallback: try going up directories from current location
    project_root = Path(
        __file__
    ).parent.parent.parent  # tests/performance -> tests -> project_root
    sys.path.insert(0, str(project_root))
    print(f"Using fallback project root: {project_root}")

from src.utils.audio_utils import get_audio_streaming_manager, get_optimal_buffer_size
from src.utils.tts_service import TTSConfig, TTSService


async def test_connection_pooling():
    """Test connection pooling functionality."""
    print("Testing connection pooling...")

    tts_service = None
    try:
        # Create TTS service
        config = TTSConfig(
            api_key=os.getenv("ELEVEN_LABS_API_KEY", "test_key"),
            enabled=bool(os.getenv("ELEVEN_LABS_API_KEY")),
        )

        tts_service = TTSService(config)

        # Test connection pool stats
        pool_stats = tts_service.connection_pool.get_stats()
        print(f"Connection pool stats: {pool_stats}")
        assert pool_stats is not None, "Connection pool stats should not be None"

        # Test performance stats
        perf_stats = tts_service.get_performance_stats()
        print(f"Performance stats: {perf_stats}")
        assert perf_stats is not None, "Performance stats should not be None"

    finally:
        if tts_service:
            await tts_service.cleanup_resources()


def create_test_config():
    """Create a test configuration."""
    return TTSConfig(
        api_key=os.getenv("ELEVEN_LABS_API_KEY", "test_key"),
        enabled=bool(os.getenv("ELEVEN_LABS_API_KEY")),
    )


def test_memory_monitoring():
    """Test memory monitoring functionality."""
    print("Testing memory monitoring...")

    config = create_test_config()

    tts_service = TTSService(config)

    try:
        # Test memory usage stats
        memory_stats = tts_service.memory_monitor.get_memory_usage()
        print(f"Memory usage: {memory_stats}")
        assert memory_stats is not None, "Memory stats should not be None"

        # Test cleanup
        cleanup_results = tts_service.memory_monitor.cleanup_memory(tts_service.cache)
        print(f"Memory cleanup results: {cleanup_results}")
        assert cleanup_results is not None, "Cleanup results should not be None"
    finally:
        # Explicitly cleanup resources
        if hasattr(tts_service, "cleanup_resources"):
            # Note: This would need to be made async if cleanup_resources is async
            pass  # or implement sync cleanup method

    print("✅ Memory monitoring test completed")


def test_buffer_optimization():
    """Test optimized buffer sizes."""
    print("Testing buffer size optimization...")

    # Test different scenarios
    test_cases = [
        (1024, False, "default"),  # Small file, not cached
        (1024, True, "default"),  # Small file, cached
        (1024 * 1024, False, "default"),  # Large file, not cached
        (32768, False, "low_latency"),  # Medium file, low latency
        (1024 * 1024, False, "high_throughput"),  # Large file, high throughput
    ]

    for audio_size, is_cached, connection_type in test_cases:
        buffer_size = get_optimal_buffer_size(audio_size, is_cached, connection_type)
        print(
            f"Audio size: {audio_size:,} bytes, cached: {is_cached}, "
            f"connection: {connection_type} -> buffer: {buffer_size:,} bytes"
        )

    print("✅ Buffer optimization test completed")


def test_streaming_manager():
    """Test streaming manager with resource cleanup."""
    print("Testing streaming manager...")

    manager = get_audio_streaming_manager()

    try:
        # Test status
        status = manager.get_stream_status()
        print(f"Streaming status: {status}")
        assert status is not None, "Stream status should not be None"

        # Test optimization
        optimization_results = manager.optimize_streaming_performance()
        print(f"Streaming optimization results: {optimization_results}")
        assert optimization_results is not None, (
            "Optimization results should not be None"
        )

    finally:
        # Cleanup streaming manager resources if needed
        pass


async def test_performance_optimization():
    """Test overall performance optimization."""
    print("Testing performance optimization...")

    config = create_test_config()

    tts_service = TTSService(config)

    try:
        # Test optimization
        optimization_results = tts_service.optimize_performance()
        print(f"TTS optimization results: {optimization_results}")
        assert optimization_results is not None, (
            "Optimization results should not be None"
        )

        # Test comprehensive stats
        comprehensive_stats = tts_service.get_performance_stats()
        print(f"Comprehensive performance stats: {comprehensive_stats}")
        assert comprehensive_stats is not None, "Comprehensive stats should not be None"

    finally:
        if tts_service:
            await tts_service.cleanup_resources()
        print("✅ Performance optimization test completed")


async def main():
    """Run all performance optimization tests."""
    print("🚀 Starting TTS Performance Optimization Tests")
    print("=" * 50)

    try:
        # Test connection pooling
        await test_connection_pooling()
        print()

        # Test memory monitoring
        test_memory_monitoring()
        print()

        # Test buffer optimization
        test_buffer_optimization()
        print()

        # Test streaming manager
        test_streaming_manager()
        print()

        # Test performance optimization
        await test_performance_optimization()
        print()

        print("✅ All performance optimization tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
