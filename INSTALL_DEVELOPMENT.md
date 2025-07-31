# Development Installation Guide

## Making the Project Installable

To avoid path manipulation in tests and enable proper imports, install the project in development mode:

```bash
# Install the project in editable/development mode
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Benefits of Installable Package

1. **No path hacks**: Tests can use standard absolute imports
2. **Better IDE support**: IDEs can properly resolve imports
3. **Consistent imports**: Same import style in tests and production code
4. **Test discovery**: pytest can discover tests without import issues
5. **CI/CD friendly**: Works reliably in different environments

## Current vs Preferred Import Style

### Current (with path hack):
```python
from test_utils import setup_src_path
setup_src_path()
from utils.multi_tier_audio_cache import MultiTierAudioCache
```

### Preferred (with installable package):
```python
from btc_max_knowledge_agent.utils.multi_tier_audio_cache import MultiTierAudioCache
```

## Migration Steps

1. Install the project: `pip install -e .`
2. Update test imports to use absolute imports
3. Remove `setup_src_path()` calls from tests
4. Update CI/CD to install the project before running tests

## Project Structure

The `pyproject.toml` is already configured for installation:
- Package name: `btc_max_knowledge_agent`
- Source directory: `src/`
- Package discovery: Automatic from `src/btc_max_knowledge_agent*`