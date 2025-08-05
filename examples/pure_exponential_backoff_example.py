#!/usr/bin/env python3
"""
Pure Exponential Backoff Helper Example

This example demonstrates how to use the pure exponential backoff function
next_backoff(prev: float) -> float that doubles the delay up to a sane ceiling
(5 minutes) and resets on successful long-running execution.
"""

import random
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.exponential_backoff import (DEFAULT_MAX_DELAY, backoff_sequence,
                                       next_backoff, reset_backoff,
                                       total_backoff_time)


def simulate_api_call() -> bool:
    """Simulate an API call that fails 70% of the time."""
    return random.random() > 0.7


def example_retry_with_exponential_backoff():
    """Example of using next_backoff for retry logic."""
    print("🔄 Exponential Backoff Retry Example")
    print("=" * 50)

    current_delay = 0  # Start fresh (0 triggers initial delay)
    max_attempts = 10

    for attempt in range(1, max_attempts + 1):
        print(f"\n📞 Attempt {attempt}/{max_attempts}")

        # Simulate API call
        success = simulate_api_call()

        if success:
            print("✅ API call succeeded!")
            # Reset backoff for future operations since we had success
            reset_delay = reset_backoff()
            print(f"🔄 Backoff reset to {reset_delay}s for future operations")
            break
        else:
            print("❌ API call failed")

            if attempt < max_attempts:
                # Calculate next backoff delay
                current_delay = next_backoff(current_delay)
                print(f"⏳ Waiting {current_delay}s before retry...")
                print(
                    f"   (Ceiling: {DEFAULT_MAX_DELAY}s = {DEFAULT_MAX_DELAY/60:.1f} minutes)"
                )

                # In real usage, you would use time.sleep(current_delay)
                # For demo purposes, we'll just show a shorter delay
                time.sleep(min(current_delay, 2.0))  # Cap demo delay at 2s
            else:
                print("💀 All attempts exhausted")


def demonstrate_backoff_sequences():
    """Demonstrate backoff sequence generation."""
    print("\n📊 Backoff Sequence Examples")
    print("=" * 50)

    # Default sequence
    print("\n1. Default sequence (10 attempts):")
    sequence = backoff_sequence(10)
    for i, delay in enumerate(sequence, 1):
        minutes = delay / 60
        print(f"   Attempt {i:2d}: {delay:6.1f}s ({minutes:5.2f} min)")

    total = total_backoff_time(10)
    print(f"   Total delay: {total:6.1f}s ({total/60:.2f} minutes)")

    # Custom sequence with lower ceiling
    print("\n2. Custom sequence (max 30s ceiling, 8 attempts):")
    sequence = backoff_sequence(8, max_delay=30.0)
    for i, delay in enumerate(sequence, 1):
        print(f"   Attempt {i}: {delay:4.1f}s")

    total = total_backoff_time(8, max_delay=30.0)
    print(f"   Total delay: {total:.1f}s")

    # Triple multiplier sequence
    print("\n3. Aggressive backoff (3x multiplier, 5 attempts):")
    sequence = backoff_sequence(5, multiplier=3.0)
    for i, delay in enumerate(sequence, 1):
        minutes = delay / 60
        print(f"   Attempt {i}: {delay:6.1f}s ({minutes:5.2f} min)")


def demonstrate_pure_function_properties():
    """Demonstrate that the functions are pure (no side effects)."""
    print("\n🧪 Pure Function Properties")
    print("=" * 50)

    # Same input always produces same output
    print("✓ Deterministic behavior:")
    for i in range(5):
        result = next_backoff(4.0)
        print(f"   next_backoff(4.0) = {result}")

    # Functions don't modify inputs
    print("\n✓ No side effects on inputs:")
    original_value = 8.0
    input_value = original_value
    result = next_backoff(input_value)
    print(f"   Input before: {original_value}")
    print(f"   Input after:  {input_value}")
    print(f"   Result:       {result}")
    print(f"   Input unchanged: {input_value == original_value}")

    # No global state
    print("\n✓ No global state:")
    sequence1 = backoff_sequence(3)
    sequence2 = backoff_sequence(3)
    print(f"   First call:  {sequence1}")
    print(f"   Second call: {sequence2}")
    print(f"   Identical:   {sequence1 == sequence2}")


def demonstrate_ceiling_behavior():
    """Demonstrate the 5-minute ceiling behavior."""
    print("\n🏔️  Ceiling Behavior (5 minutes = 300s)")
    print("=" * 50)

    delays = [100, 150, 200, 250, 300, 400, 500]

    for delay in delays:
        next_delay = next_backoff(delay)
        capped = next_delay >= DEFAULT_MAX_DELAY
        status = "CAPPED" if capped else "normal"
        print(f"   {delay:3.0f}s → {next_delay:3.0f}s ({status})")


def main():
    """Run all examples."""
    print("🚀 Pure Exponential Backoff Helper Examples")
    print("=" * 60)

    # Set seed for reproducible demo
    random.seed(42)

    example_retry_with_exponential_backoff()
    demonstrate_backoff_sequences()
    demonstrate_pure_function_properties()
    demonstrate_ceiling_behavior()

    print("\n" + "=" * 60)
    print("✨ Examples completed!")
    print("\nKey features:")
    print("• Pure function - no side effects")
    print("• Doubles delay each time (configurable)")
    print("• 5-minute ceiling (300s) by default")
    print("• Reset capability for successful operations")
    print("• Utility functions for sequence analysis")


if __name__ == "__main__":
    main()
