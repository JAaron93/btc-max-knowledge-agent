#!/bin/bash

# Test runner script for btc-max-knowledge-agent
# This script provides robust test execution with proper PYTHONPATH setup

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set PYTHONPATH to include project root and src directory
export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/src:${PYTHONPATH}"

echo "🧪 BTC Max Knowledge Agent Test Runner (Shell)"
echo "================================================"
echo "📁 Project root: ${SCRIPT_DIR}"
echo "🐍 PYTHONPATH: ${PYTHONPATH}"
echo ""

# Function to run tests with pytest
run_tests() {
    echo "🚀 Running: python -m pytest $@"
    echo "==============================="
    
    cd "${SCRIPT_DIR}" || exit 1
    python -m pytest "$@"
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo ""
        echo "✅ All tests passed!"
    else
        echo ""
        echo "❌ Tests failed with exit code $exit_code"
    fi
    
    return $exit_code
}

# Check if arguments were provided
if [ $# -eq 0 ]; then
    echo "Running all tests with verbose output..."
    run_tests -v --tb=short --color=yes
else
    echo "Running tests with arguments: $@"
    run_tests "$@"
fi

exit $?
