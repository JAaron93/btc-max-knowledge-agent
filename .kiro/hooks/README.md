# Kiro Agent Hooks

This directory contains agent hooks that automate various project management tasks.

## Available Hooks

### Spec Completion Monitor

**File:** `spec-completion-monitor.json`
**Script:** `spec-completion-agent.py`

Automatically monitors spec directories and creates completion status files when all tasks are marked as completed.

#### Features

- **Automatic Detection**: Monitors `tasks.md` files for completion status
- **Status Files**: Creates `.completed` files with completion metadata
- **Summary Generation**: Generates `COMPLETION_SUMMARY.md` documents
- **Batch Processing**: Can scan all specs or target specific ones

#### Usage

**Automatic (via Kiro IDE):**
The hook automatically triggers when you save changes to any `tasks.md` file in `.kiro/specs/*/`.

**Manual Execution:**
```bash
# Check all specs
.kiro/hooks/check-spec-completion.sh

# Check specific spec
.kiro/hooks/check-spec-completion.sh real-time-tts-integration

# Direct Python execution
python .kiro/hooks/spec-completion-agent.py .kiro/specs/real-time-tts-integration
python .kiro/hooks/spec-completion-agent.py --scan-all
```

#### Output Files

When a spec is completed, the hook creates:

1. **`.completed`** - Status file with completion metadata
2. **`COMPLETION_SUMMARY.md`** - Human-readable completion summary

#### Example `.completed` File

```
# Spec Completion Status
SPEC_COMPLETED=true
COMPLETION_DATE=2025-01-26
SPEC_NAME=Real Time Tts Integration
TOTAL_TASKS=12
COMPLETED_TASKS=12
STATUS=All tasks completed successfully
IMPLEMENTATION_READY=true

# Task Summary
TASK_1=Set up core TTS service infrastructure
TASK_2=Implement robust audio caching system
...

# Completion Details
COMPLETION_TIMESTAMP=2025-01-26T10:30:00.123456
AGENT_HOOK_VERSION=1.0
AUTO_GENERATED=true
```

## Hook Configuration

### JSON Configuration Format

```json
{
  "name": "Hook Name",
  "description": "What this hook does",
  "trigger": {
    "type": "file_save",
    "patterns": ["file/patterns/to/watch"]
  },
  "actions": [
    {
      "type": "agent_execution",
      "prompt": "Instructions for the agent",
      "context_files": ["files", "to", "include"]
    }
  ],
  "settings": {
    "enabled": true,
    "auto_approve": false
  }
}
```

### Trigger Types

- **`file_save`**: Triggers when specified files are saved
- **`file_change`**: Triggers on any file modification
- **`manual`**: Only triggered manually by user
- **`scheduled`**: Runs on a schedule (future enhancement)

### Action Types

- **`agent_execution`**: Runs an AI agent with specific instructions
- **`script_execution`**: Runs a shell script or Python script
- **`notification`**: Sends a notification to the user

## Creating New Hooks

### 1. Create Hook Configuration

Create a JSON file in `.kiro/hooks/` with your hook configuration:

```json
{
  "name": "My Custom Hook",
  "description": "Does something useful",
  "trigger": {
    "type": "file_save",
    "patterns": ["src/**/*.py"]
  },
  "actions": [
    {
      "type": "agent_execution",
      "prompt": "Review the Python code changes and suggest improvements",
      "context_files": ["{modified_file}"]
    }
  ],
  "settings": {
    "enabled": true,
    "auto_approve": false
  }
}
```

### 2. Create Supporting Scripts (Optional)

If your hook needs custom logic, create Python or shell scripts:

```python
#!/usr/bin/env python3
"""
My Custom Hook Script
"""

def main():
    # Your custom logic here
    pass

if __name__ == '__main__':
    main()
```

### 3. Test Your Hook

Use the manual trigger scripts to test your hook before enabling automatic triggers.

## Best Practices

### Hook Design

1. **Single Responsibility**: Each hook should do one thing well
2. **Idempotent**: Hooks should be safe to run multiple times
3. **Fast Execution**: Keep hook execution time minimal
4. **Error Handling**: Handle errors gracefully and provide useful feedback
5. **Logging**: Include appropriate logging for debugging

### File Patterns

- Use specific patterns to avoid unnecessary triggers
- Consider performance impact of broad patterns
- Test patterns thoroughly before deployment

### Agent Instructions

- Be specific and clear in agent prompts
- Include relevant context files
- Consider the agent's capabilities and limitations
- Test agent responses with various scenarios

## Troubleshooting

### Hook Not Triggering

1. Check that the hook is enabled in settings
2. Verify file patterns match the files you're modifying
3. Check Kiro IDE hook status in the Agent Hooks panel
4. Review hook logs for error messages

### Script Execution Errors

1. Ensure scripts have proper permissions (`chmod +x`)
2. Check Python path and dependencies
3. Verify file paths are correct (relative to project root)
4. Test scripts manually before using in hooks

### Performance Issues

1. Optimize file patterns to be more specific
2. Consider debouncing for frequently modified files
3. Use async operations where possible
4. Monitor hook execution times

## Future Enhancements

Planned improvements for the hooks system:

- **Scheduled Hooks**: Time-based triggers
- **Conditional Logic**: More complex trigger conditions
- **Hook Dependencies**: Chain hooks together
- **Performance Monitoring**: Track hook execution metrics
- **Hook Templates**: Pre-built hooks for common tasks
- **Integration APIs**: Connect with external services

## Contributing

When adding new hooks:

1. Follow the established naming conventions
2. Include comprehensive documentation
3. Add test cases for your hook logic
4. Consider backward compatibility
5. Update this README with your new hook

## Support

For issues with hooks:

1. Check the troubleshooting section above
2. Review hook logs and error messages
3. Test hooks manually using the provided scripts
4. Consult the Kiro IDE documentation for hook features