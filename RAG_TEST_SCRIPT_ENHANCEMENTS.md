# RAG Test Script Enhancements

## Improvements Made

### 1. Enhanced Test Script (`tests/test_rag_system.py`)

**New Command Line Options:**
- `--verbose` / `-v`: Enable verbose output with detailed error information
- `--debug` / `-d`: Enable debug mode to show request details and endpoint info  
- `--endpoint`: Override the API endpoint URL (alternative to environment variable)
- `--help` / `-h`: Show all available options

**Enhanced Features:**
- ✅ **Argument parsing**: Added `argparse` support for better CLI experience
- ✅ **Debug mode**: Shows request payload, headers, and endpoint details
- ✅ **Verbose error reporting**: Displays full error details and tracebacks
- ✅ **Flexible endpoint configuration**: Command-line override option
- ✅ **Better error handling**: More detailed error information for troubleshooting

### 2. Updated Documentation (`README.md`)

**Added Information:**
- ✅ **Dependency requirements**: Clarified that `requests` is included in main dependencies
- ✅ **Command-line examples**: Multiple usage examples with different options
- ✅ **Option descriptions**: Detailed explanation of all available flags
- ✅ **Debug usage examples**: How to run with increased verbosity

**New Usage Examples:**
```bash
# Basic usage
python tests/test_rag_system.py

# With verbose output
python tests/test_rag_system.py --verbose

# With debug information
python tests/test_rag_system.py --debug

# Custom endpoint via CLI
python tests/test_rag_system.py --endpoint "http://staging:8000/query"

# Combined options
python tests/test_rag_system.py --verbose --debug
```

## Benefits

### For Developers:
- **Better debugging**: Debug mode shows exactly what's being sent to the API
- **Clearer error messages**: Verbose mode provides full error details and tracebacks
- **Flexible testing**: Easy endpoint switching for different environments
- **Professional CLI**: Standard argument parsing with help documentation

### For Documentation:
- **Clear dependencies**: Users know exactly what packages are needed
- **Usage examples**: Multiple scenarios covered with practical examples
- **Self-documenting**: Built-in help system with `--help` flag

## Testing Verification
- ✅ Help system works correctly
- ✅ Debug mode shows request details and endpoint information
- ✅ Verbose mode provides detailed error information
- ✅ Endpoint override functionality works
- ✅ All existing functionality preserved