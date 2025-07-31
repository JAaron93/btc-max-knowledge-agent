# Test Path Setup Solution

## Problem Solved

Previously, multiple test files were calling `setup_src_path()` individually, which caused:
- Redundant sys.path modifications
- Order-dependent import issues
- Potential test discovery failures
- Code duplication across test files

## Solution Implemented

### 1. Centralized Path Setup in conftest.py

The `setup_src_path()` call has been moved to `tests/conftest.py`:

```python
# Set up src path once per test session to avoid repeated sys.path modifications
# This eliminates the need for individual test files to call setup_src_path()
from test_utils import setup_src_path
setup_src_path()
```

### 2. Updated Test Files

All test files have been updated to remove redundant `setup_src_path()` calls:

**Before:**
```python
from test_utils import setup_src_path
setup_src_path()
from agents.pinecone_assistant_agent import PineconeAssistantAgent
```

**After:**
```python
# NOTE: setup_src_path() is now called once in conftest.py to avoid redundant sys.path modifications
from agents.pinecone_assistant_agent import PineconeAssistantAgent
```

### 3. Files Updated

- `tests/test_pinecone_assistant_url_metadata.py` - Main target file
- `tests/test_security_middleware_simple.py`
- `tests/test_build_upload_payload.py`
- `tests/test_logging_performance.py`
- `tests/test_multi_tier_cache.py`
- `tests/test_pinecone_url_metadata_prod.py`

## Benefits

1. **Single Point of Setup**: Path setup happens once per test session
2. **No Redundancy**: Eliminates repeated sys.path modifications
3. **Order Independence**: Tests don't need to worry about import order
4. **Cleaner Code**: Removes boilerplate from individual test files
5. **Better Performance**: Avoids repeated path resolution and checking

## How It Works

1. When pytest runs, it automatically loads `conftest.py`
2. `conftest.py` calls `setup_src_path()` once at the session level
3. All test files can now import from `src/` without additional setup
4. The existing guard in `setup_src_path()` prevents duplicate additions

## Future Migration

The ultimate solution is still to make the project installable:

```bash
pip install -e .
```

This would eliminate the need for any path manipulation and allow standard absolute imports:

```python
from btc_max_knowledge_agent.agents.pinecone_assistant_agent import PineconeAssistantAgent
```

## Testing the Solution

To verify the solution works:

```bash
# Run a specific test
python -m pytest tests/test_pinecone_assistant_url_metadata.py -v

# Run all tests
python -m pytest tests/ -v
```

The tests should run without any import errors or path-related issues.