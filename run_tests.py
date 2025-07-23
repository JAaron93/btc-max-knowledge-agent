#!/usr/bin/env python3
"""
Test runner script for btc-max-knowledge-agent

This script provides a robust way to run tests with proper Python path configuration.
It eliminates the need for fragile sys.path.append() calls in test files.

Usage:
    python run_tests.py                          # Run all tests
    python run_tests.py test_pinecone_*          # Run specific test pattern
    python run_tests.py --verbose                # Run with verbose output
    python run_tests.py --help                   # Show help
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def setup_environment():
    """Setup environment variables for proper test execution."""
    project_root = Path(__file__).parent.resolve()

    # Set PYTHONPATH to include project root and src directory
    python_path = [
        str(project_root),
        str(project_root / "src"),
    ]

    # Add to existing PYTHONPATH if it exists
    existing_path = os.environ.get("PYTHONPATH", "")
    if existing_path:
        python_path.append(existing_path)

    os.environ["PYTHONPATH"] = os.pathsep.join(python_path)

    print(f"📁 Project root: {project_root}")
    print(f"🐍 PYTHONPATH: {os.environ['PYTHONPATH']}")
    print()


def run_tests(test_args=None, verbose=False):
    """Run tests using pytest with proper configuration."""

    # Base pytest command
    cmd = [sys.executable, "-m", "pytest"]

    # Add default arguments
    default_args = ["-v" if verbose else "-q", "--tb=short", "--color=yes"]
    cmd.extend(default_args)

    # Add user-specified test arguments
    if test_args:
        cmd.extend(test_args)

    print(f"🚀 Running command: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test runner for btc-max-knowledge-agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                                    # Run all tests
  python run_tests.py test_pinecone_*                    # Run specific pattern
  python run_tests.py test_pinecone_assistant_url_metadata_enhanced.py  # Run specific file
  python run_tests.py --verbose                          # Run with verbose output
  python run_tests.py -k "test_url"                     # Run tests matching pattern
  python run_tests.py --collect-only                    # Just show what tests would run
        """,
    )

    parser.add_argument(
        "tests", nargs="*", help="Test files or patterns to run (default: discover all)"
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Run tests with verbose output"
    )

    parser.add_argument(
        "-k", "--keyword", help="Run tests matching given substring expression"
    )

    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Just collect and show tests, don't run them",
    )


    args = parser.parse_args()

    print("🧪 BTC Max Knowledge Agent Test Runner")
    print("=" * 50)

    # Setup environment
    setup_environment()

    # Build test arguments
    test_args = []

    if args.tests:
        test_args.extend(args.tests)

    if args.keyword:
        test_args.extend(["-k", args.keyword])

    if args.collect_only:
        test_args.append("--collect-only")

    # Run tests
    exit_code = run_tests(test_args, args.verbose)

    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {exit_code}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
