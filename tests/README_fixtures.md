# Pytest Fixtures for URL Metadata Logging

This document describes the reusable pytest fixtures available in `conftest.py` for testing URL metadata logging functionality.

## Overview

The fixtures provide standardized, reusable components for testing query truncation configuration and URL metadata logging operations. They eliminate code duplication and ensure consistent test setups across the test suite.

## Available Fixtures

### Configuration Fixtures

#### `QueryTruncationConfig` Class
A dataclass representing query truncation configuration:
```python
@dataclass
class QueryTruncationConfig:
    query_truncation_length: int = 100
    log_dir: str = "logs"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
```

#### Individual Config Fixtures

- **`default_query_config`**: Default configuration (100 character truncation)
- **`custom_query_config`**: Custom configuration (200 character truncation)  
- **`short_query_config`**: Short configuration (50 character truncation)

```python
def test_default_config(default_query_config):
    assert default_query_config.query_truncation_length == 100
```

#### `config_variants`
Provides multiple configuration variants for comprehensive testing:
```python
def test_all_configs(config_variants):
    for name, config in config_variants.items():
        # Test each variant: 'default', 'custom', 'short', 'extended', 'minimal'
        logger = URLMetadataLogger(query_truncation_length=config.query_truncation_length)
```

### Directory and File Fixtures

#### `temp_config_dir(tmp_path)`
Creates a temporary directory structure with pre-populated config files:
- `config/basic_config.json` - Standard configuration
- `config/custom_config.json` - Custom truncation length
- `config/minimal_config.json` - Minimal configuration
- `logs/sample.log` - Sample log entries
- `test_data/` - Directory for test data

```python
def test_config_loading(temp_config_dir):
    config_file = temp_config_dir / "config" / "basic_config.json"
    assert config_file.exists()
```

#### `session_temp_dir`
Session-scoped temporary directory for expensive setup operations:
```python
def test_session_setup(session_temp_dir):
    # Use for operations that can be shared across tests
    shared_file = session_temp_dir / "shared_data.json"
```

### Logger Fixtures

#### `mock_url_metadata_logger`
Provides a real `URLMetadataLogger` instance with temporary directory:
```python
def test_logger_operations(mock_url_metadata_logger):
    mock_url_metadata_logger.log_retrieval("test query", 5, 100.0)
    assert mock_url_metadata_logger.config['query_truncation_length'] == 100
```

### Test Data Fixtures

#### `sample_test_data`
Provides comprehensive test data including URLs, queries, and expected truncation results:
```python
def test_with_sample_data(sample_test_data):
    urls = sample_test_data['urls']  # Bitcoin-related URLs
    queries = sample_test_data['queries']  # Various query lengths
    expected = sample_test_data['expected_truncations']  # Expected truncation results
```

#### `parameterized_logger_configs`
List of logger configuration dictionaries for parameterized tests:
```python
@pytest.mark.parametrize("config", parameterized_logger_configs())
def test_logger_with_config(config):
    logger = URLMetadataLogger(**config)
```

## Parametrized Test Decorators

### `@pytest_parametrize_truncation_lengths`
Tests multiple truncation lengths: [25, 50, 100, 200, 500]
```python
@pytest_parametrize_truncation_lengths
def test_various_lengths(truncation_length, temp_config_dir):
    # Test runs 5 times with different truncation lengths
```

### `@pytest_parametrize_config_variants`
Tests multiple configuration variants:
```python
@pytest_parametrize_config_variants
def test_config_variants(config_name, config, temp_config_dir):
    # Test runs for each: "default", "custom", "short", "extended"
```

## Usage Examples

### Basic Configuration Testing
```python
class TestQueryTruncation:
    def test_default_config(self, default_query_config, temp_config_dir):
        logger_dir = temp_config_dir / "logs" / "default"
        logger_dir.mkdir(parents=True, exist_ok=True)
        
        logger = URLMetadataLogger(
            log_dir=str(logger_dir),
            query_truncation_length=default_query_config.query_truncation_length
        )
        
        assert logger.config['query_truncation_length'] == 100
```

### Parametrized Testing
```python
class TestParametrized:
    @pytest_parametrize_truncation_lengths
    def test_all_lengths(self, truncation_length, temp_config_dir):
        logger = URLMetadataLogger(
            log_dir=str(temp_config_dir / "logs"),
            query_truncation_length=truncation_length
        )
        
        test_query = "A" * 300  # Long query
        logger.log_retrieval(test_query, 1, 50.0)
        
        assert logger.config['query_truncation_length'] == truncation_length
```

### Combined Fixtures
```python
def test_comprehensive(self, temp_config_dir, config_variants, sample_test_data):
    for config_name, config in config_variants.items():
        logger_dir = temp_config_dir / "logs" / config_name
        logger_dir.mkdir(parents=True, exist_ok=True)
        
        logger = URLMetadataLogger(
            log_dir=str(logger_dir),
            query_truncation_length=config.query_truncation_length
        )
        
        # Test with sample data
        for query in sample_test_data['queries']:
            logger.log_retrieval(query, 1, 100.0)
```

## Migration from Old Tests

### Before (Manual Setup)
```python
def test_old_style():
    temp_dir = tempfile.mkdtemp()
    try:
        logger = URLMetadataLogger(log_dir=temp_dir, query_truncation_length=100)
        # ... test logic ...
    finally:
        shutil.rmtree(temp_dir)
```

### After (Using Fixtures)
```python
def test_new_style(self, mock_url_metadata_logger):
    # Temporary directory and cleanup handled automatically
    mock_url_metadata_logger.log_retrieval("test query", 1, 50.0)
    assert mock_url_metadata_logger.config['query_truncation_length'] == 100
```

## Benefits

1. **Reduced Duplication**: Common setup code is centralized in fixtures
2. **Automatic Cleanup**: Temporary directories are automatically cleaned up
3. **Consistent Data**: Standardized test data across all tests
4. **Parameterization**: Easy testing of multiple configurations
5. **Maintainability**: Changes to test setup only require updates to fixtures
6. **Readability**: Test intent is clearer without setup boilerplate

## File Structure

```
tests/
├── conftest.py                    # Fixture definitions
├── test_query_truncation_config.py  # Updated to use fixtures
├── test_fixtures_example.py         # Usage examples
└── README_fixtures.md               # This documentation
```

## Running Tests

```bash
# Run all tests using fixtures
pytest tests/

# Run specific fixture tests
pytest tests/test_fixtures_example.py -v

# Run parametrized tests only
pytest tests/ -k "parametrize" -v

# Run tests with specific truncation length
pytest tests/ -k "truncation_length" -v
```
