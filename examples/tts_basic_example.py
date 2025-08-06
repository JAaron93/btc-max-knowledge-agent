#!/usr/bin/env python3
"""
Basic example of using the TTS service.
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path (only if it exists)
src_path = Path(__file__).parent.parent / "src"
if src_path.exists() and src_path.is_dir():
    sys.path.insert(0, str(src_path))
else:
    print(f"Warning: src directory not found at {src_path}")
    print(
        "Please ensure the script is run from the correct location or adjust the path."
    )

from utils.tts_service import TTSError, get_tts_service  # noqa: E402


async def main():
    """Demonstrate basic TTS functionality."""
    print("TTS Service Basic Example")
    print("=" * 30)

    # Get TTS service instance
    tts = get_tts_service()

    if not tts.is_enabled():
        print("TTS service is not enabled. Please check your ELEVEN_LABS_API_KEY.")
        return

    # Example text to synthesize
    text = "Hello! This is a demonstration of the Bitcoin Knowledge Agent's text-to-speech functionality."

    try:
        print(f"Synthesizing: {text}")
        print("Please wait...")

        # Synthesize text to audio
        audio_data = await tts.synthesize_text(text)

        print(f"✓ Successfully generated {len(audio_data)} bytes of audio")

        # Save to file for testing
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"example_output_{timestamp}.mp3"

        try:
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"✓ Audio saved to {output_file}")
        except IOError as e:
            print(f"✗ Failed to save audio file: {e}")
            return

        # Test cache functionality
        print("\nTesting cache...")
        cached_audio = await tts.synthesize_text(text)

        # Check if cache is working by comparing length and first few bytes
        if (
            len(cached_audio) == len(audio_data)
            and cached_audio[:100] == audio_data[:100]
        ):
            print("✓ Cache working - similar audio returned instantly")
        else:
            print("✗ Cache issue - different audio returned")
            print(f"  Original: {len(audio_data)} bytes")
            print(f"  Cached: {len(cached_audio)} bytes")

        # Show cache stats
        stats = tts.get_cache_stats()
        print(f"Cache stats: {stats}")

    except TTSError as e:
        print(f"TTS Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
