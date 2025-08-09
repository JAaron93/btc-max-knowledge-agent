#!/usr/bin/env python3
"""
Test script to verify the logging optimization in demo_url_metadata_complete.py
"""

import sys
import time
from io import StringIO
from contextlib import redirect_stdout

# Import the demo class
from examples.demo_url_metadata_complete import URLMetadataDemo


def test_logging_optimization():
    """Test that the logging optimization reduces stdout output."""
    print("Testing logging optimization...")
    
    # Create demo instance
    demo = URLMetadataDemo()
    
    # Create test data with varying sizes to test throttling
    test_datasets = [
        # Small dataset (should show all progress)
        [{"id": f"item_{i}", "metadata": {"source_url": f"https://example.com/{i}"}} for i in range(5)],
        # Medium dataset (should show throttled progress)
        [{"id": f"item_{i}", "metadata": {"source_url": f"https://example.com/{i}"}} for i in range(25)],
    ]
    
    f
    ---")
        
        # Capture stdout to count print statements
        )
        
        start_time = time.time()
        _output):
            results = demo.demonons(data)
        end_time = time.time()
        
        # Analyze output
        
        progress_lines =
        
        print(f"  ✓ Processed {len(results)} items in {end_time - start_time:.2}s")
        
        print(f"  ✓ Output reduction: {((len(data) - len(progress_lines)) / len(data
        
        # Verify all items were processed
        
        
        # Show sample progrnes
        if progress_lines:
            print(f"  Sample progress: {progress_lines[0]}")
            is) > 1:
                print(f"                   {progress_lines)
    
    prin


if __nam_":
    test_logging_optimization()