#!/usr/bin/env python3
"""
Test runner script for btc-max-knowledge-agent

This script defers to pytest.ini for discovery
(testpaths=tests, pythonpath=src) and avoids manual
PYTHONPATH mutation. It provides convenience marker flags.

Usage:
    python run_tests.py                    # Run all tests (quiet)
    python run_tests.py -v                 # Verbose
    python run_tests.py -k "expr"          # Keyword selection
    python run_tests.py --unit             # Only unit tests
    python run_tests.py --integration      # Only integration tests
    python run_tests.py --e2e              # Only e2e tests
    python run_tests.py --performance      # Only performance tests
    python run_tests.py --ui               # Only ui tests
    python run_tests.py --security         # Only security tests
    python run_tests.py --collect-only     # Collection only
"""

import argparse
import subprocess
import sys
from typing import List


MARKER_FLAGS = {
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
    "performance": "performance",
    "ui": "ui",
    "security": "security",
}


def build_marker_expr(args: argparse.Namespace) -> str:
    selected: List[str] = []
    for flag, marker in MARKER_FLAGS.items():
        if getattr(args, flag, False):
            selected.append(marker)
    if not selected:
        return ""
    # Join with or to include any of the selected markers
    return " or ".join(selected)


def run_tests(test_args=None, verbose=False):
    """Run tests using pytest with proper configuration."""
    cmd = [sys.executable, "-m", "pytest"]
    default_args = ["-v" if verbose else "-q", "--tb=short", "--color=yes"]
    cmd.extend(default_args)

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
  python run_tests.py                            # Run all tests
  python run_tests.py -k "test_url"              # Run tests matching pattern
  python run_tests.py --unit -k "audio"          # Unit tests related to audio
  python run_tests.py --collect-only             # Just show collected tests
        """,
    )

    parser.add_argument(
        "tests",
        nargs="*",
        help=(
            "Optional test files or node ids "
            "(default: use pytest.ini testpaths)"
        ),
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Run tests with verbose output",
    )

    parser.add_argument(
        "-k", "--keyword", help="Run tests matching given substring expression"
    )

    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Just collect and show tests, don't run them",
    )

    # Marker convenience flags
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Run tests marked as unit",
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run tests marked as integration",
    )
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="Run tests marked as e2e",
    )
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Run tests marked as performance",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Run tests marked as ui",
    )
    parser.add_argument(
        "--security",
        action="store_true",
        help="Run tests marked as security",
    )

    args = parser.parse_args()

    print("🧪 BTC Max Knowledge Agent Test Runner")
    print("=" * 50)

    # Build test arguments; rely on pytest.ini for discovery by default
    test_args: List[str] = []

    if args.tests:
        test_args.extend(args.tests)

    marker_expr = build_marker_expr(args)
    if marker_expr:
        test_args.extend(["-m", marker_expr])

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
