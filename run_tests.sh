#!/bin/bash

# Test runner script for btc-max-knowledge-agent (shell)
# Relies on pytest.ini (testpaths=tests, pythonpath=src); no PYTHONPATH hacks.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧪 BTC Max Knowledge Agent Test Runner (Shell)"
echo "================================================"
echo "📁 Project root: ${SCRIPT_DIR}"
echo ""

run_tests() {
    echo "🚀 Running: python -m pytest $*"
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

# Convenience: map high-level flags to pytest -m expressions
# Usage: ./run_tests.sh --unit [extra pytest args...]
map_flags_to_pytest_args() {
  local args=()
  local markers=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --unit) markers+=("unit"); shift ;;
      --integration) markers+=("integration"); shift ;;
      --e2e) markers+=("e2e"); shift ;;
      --performance) markers+=("performance"); shift ;;
      --ui) markers+=("ui"); shift ;;
      --security) markers+=("security"); shift ;;
      *) args+=("$1"); shift ;;
    esac
  done

  if [ ${#markers[@]} -gt 0 ]; then
    local expr
    expr=$(IFS=' or ' ; echo "${markers[*]}")
    args+=("-m" "$expr")
  fi

  # Default quiet, short tracebacks, color unless user provided verbosity already
  if [[ ! " ${args[*]} " =~ " -v " ]] && [[ ! " ${args[*]} " =~ " -q " ]]; then
    args+=("-q")
  fi
  args+=("--tb=short" "--color=yes")
  echo "${args[@]}"
}

if [ $# -eq 0 ]; then
    echo "Running all tests (quiet by default)..."
    run_tests -q --tb=short --color=yes
else
    echo "Running tests with arguments: $*"
    mapped_args=( $(map_flags_to_pytest_args "$@") )
    run_tests "${mapped_args[@]}"
fi

exit $?
