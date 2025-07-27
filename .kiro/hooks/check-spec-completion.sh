#!/bin/bash
# Manual trigger script for spec completion checking

echo "🔍 Spec Completion Monitor"
echo "=========================="

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage:"
    echo "  $0                    # Check all specs"
    echo "  $0 <spec-name>        # Check specific spec"
    echo "  $0 --scan-all         # Scan all specs (same as no args)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Check all specs"
    echo "  $0 real-time-tts-integration         # Check specific spec"
    echo "  $0 --scan-all                        # Explicit scan all"
    exit 0
fi

# Change to project root
PROJECT_ROOT="$(dirname "$0")/../.."
if ! cd "$PROJECT_ROOT"; then
    echo "❌ Failed to change to project root directory"
    exit 1
fi

# Check if the Python agent exists
AGENT_SCRIPT=".kiro/hooks/spec-completion-agent.py"
if [ ! -f "$AGENT_SCRIPT" ]; then
    echo "❌ Error: Python agent script not found: $AGENT_SCRIPT"
    echo "Please ensure the spec completion agent is properly installed."
    exit 1
fi

if [ -z "$1" ] || [ "$1" = "--scan-all" ]; then
    # No arguments or explicit scan all - scan all specs
    echo "🔍 Scanning all specs for completion..."
    python "$AGENT_SCRIPT" --scan-all
else
    # Check specific spec
    # Validate spec name (no path traversal)
    if [[ "$1" =~ \.\./|^/ ]]; then
        echo "❌ Invalid spec name: $1"
        exit 1
    fi
    SPEC_DIR=".kiro/specs/$1"
    if [ ! -d "$SPEC_DIR" ]; then
        echo "❌ Spec directory not found: $SPEC_DIR"
        echo "Available specs:"
        if [ -d ".kiro/specs" ] && [ "$(ls -A .kiro/specs 2>/dev/null)" ]; then
            ls -1 .kiro/specs/
        else
            echo "  (no specs found)"
        fi
        exit 1
    fi
    
    echo "🔍 Checking spec: $1"
    python "$AGENT_SCRIPT" "$SPEC_DIR"
fi

echo ""
echo "✨ Spec completion check complete!"