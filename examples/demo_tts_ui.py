#!/usr/bin/env python3
"""
Demo script to showcase TTS UI components
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]  # assumes repo_root/src/…
# or, more robustly:
# import importlib.util, inspect
# repo_root = Path(inspect.getfile(importlib.util.find_spec("src").loader)).parent.parent

sys.path.insert(0, str(project_root))
from src.web.bitcoin_assistant_ui import create_bitcoin_assistant_ui


def parse_args():
    """Parse command-line arguments for launch configuration."""
    parser = argparse.ArgumentParser(
        description="Demo script to showcase TTS UI components",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--host", default="127.0.0.1", help="Host address to bind the server to"
    )

    parser.add_argument(
        "--port", type=int, default=7860, help="Port number to run the server on"
    )

    parser.add_argument(
        "--share", action="store_true", help="Create a public shareable link"
    )

    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")

    parser.add_argument(
        "--no-error-display",
        action="store_true",
        help="Disable error display in the interface",
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_args()

    print("🎤 Starting TTS UI Demo...")
    print("📝 This demo showcases the new TTS controls:")
    print("   ✅ Enable Voice toggle switch")
    print("   ✅ Voice Volume slider")
    print("   ✅ Audio output component")
    print("   ✅ Waveform animation during synthesis")
    print()
    print(f"🌐 The UI will be available at http://{args.host}:{args.port}")
    if args.share:
        print("🔗 Public sharing is enabled")
    print("⚠️  Note: TTS functionality requires the backend API to be running")

    # Create and launch the interface
    interface = create_bitcoin_assistant_ui()
    interface.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        show_error=not args.no_error_display,
        quiet=args.quiet,
    )
