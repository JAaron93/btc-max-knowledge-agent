#!/usr/bin/env python3
"""
Test just the buffer optimization functionality.
"""

# Optimized streaming buffer sizes for different scenarios
STREAMING_BUFFER_SIZES = {
    'default': 8192,      # 8KB - good balance for most cases
    'low_latency': 4096,  # 4KB - for real-time applications
    'high_throughput': 16384,  # 16KB - for large files
    'mobile': 2048,       # 2KB - for mobile/low bandwidth
    'desktop': 12288      # 12KB - for desktop applications
}

def get_optimal_buffer_size(audio_size: int, is_cached: bool = False, connection_type: str = 'default') -> int:
    if audio_size < 0:
        raise ValueError("audio_size must be non-negative")
    # existing logic continues below
    base_size = _get_base_size(connection_type)
    if is_cached:
        return min(base_size, 4 * 1024)
    if audio_size < 32 * 1024:
        return min(base_size, 2 * 1024)
    if audio_size > 1 * 1024 * 1024:
        return max(base_size, 16 * 1024)
    return base_size
    """
    Calculate optimal buffer size based on audio characteristics and connection type.
    
    Args:
        audio_size: Size of audio data in bytes
        is_cached: Whether audio is from cache (instant replay)
        connection_type: Type of connection ('default', 'low_latency', 'high_throughput', 'mobile', 'desktop')
    
    Returns:
        Optimal buffer size in bytes
    """
    base_size = STREAMING_BUFFER_SIZES.get(connection_type, STREAMING_BUFFER_SIZES['default'])
    
    # For cached audio, use smaller buffers for instant playback
    if is_cached:
        return min(base_size, 4096)
    
def test_buffer_optimization():
    """Test optimized buffer sizes."""
    print("Testing buffer size optimization...")
    
    # Test different scenarios
    test_cases = [
        # (audio_size, is_cached, connection_type, expected_buffer_size)
        (1024, False, 'default', 2048),             # Small file, not cached
        (1024, True, 'default', 2048),              # Small file, cached  
        (1024 * 1024, False, 'default', 16384),     # Large file, not cached
        (32768, False, 'low_latency', 4096),        # Medium file, low latency
        (1024 * 1024, False, 'high_throughput', 16384),  # Large file, high throughput
    ]
    
    for audio_size, is_cached, connection_type, expected in test_cases:
        buffer_size = get_optimal_buffer_size(audio_size, is_cached, connection_type)
        print(f"Audio size: {audio_size:,} bytes, cached: {is_cached}, "
              f"connection: {connection_type} -> buffer: {buffer_size:,} bytes")
        
        if buffer_size != expected:
            print(f"❌ Expected {expected}, got {buffer_size}")
            return False
    
    print("✅ Buffer optimization test completed")
    return True
        (32768, False, 'low_latency'), # Medium file, low latency
        (1024 * 1024, False, 'high_throughput'),  # Large file, high throughput
    ]
    
    for audio_size, is_cached, connection_type in test_cases:
        buffer_size = get_optimal_buffer_size(audio_size, is_cached, connection_type)
        print(f"Audio size: {audio_size:,} bytes, cached: {is_cached}, "
              f"connection: {connection_type} -> buffer: {buffer_size:,} bytes")
    
    print("✅ Buffer optimization test completed")
    return True


def main():
    """Run buffer optimization test."""
    print("🚀 Testing Buffer Size Optimization")
    print("=" * 40)
    
    success = test_buffer_optimization()
    
    if success:
        print("✅ Buffer optimization test completed successfully!")
        return 0
    else:
        print("❌ Buffer optimization test failed!")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)