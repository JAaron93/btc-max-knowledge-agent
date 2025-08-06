# Automatic setup_src_path() Improvements

## Issue Addressed

**Problem**: In `tests/test_utils.py` around lines 103-104, the automatic call to `setup_src_path()` on import could cause import failures if the src directory was missing, making the module unusable in contexts where the src directory doesn't exist.

**Location**: End of `tests/test_utils.py` file

## Solution Implemented

### 1. Error Handling Around Automatic Setup

**Before (Problematic):**
```python
# Automatically set up src path when this module is imported
setup_src_path()
```

**After (Robust):**
```python
def _auto_setup_src_path() -> None:
    """
    Automatically set up src path with error handling and optional control.
    
    This function is called on module import to set up the src path. It includes:
    - Error handling to prevent import failures if src directory is missing
    - Optional control via TEST_UTILS_AUTO_SETUP environment variable
    - Graceful degradation if setup fails
    """
    import os
    
    # Check if auto setup is disabled via environment variable
    if os.getenv('TEST_UTILS_AUTO_SETUP', '1').lower() in ('0', 'false', 'no', 'off'):
        return
    
    # Attempt to set up src path with error handling
    try:
        setup_src_path()
    except FileNotFoundError as e:
        # Src directory doesn't exist - this is not necessarily an error
        # as the module might be used in contexts where src isn't available
        pass
    except Exception as e:
        # Other unexpected errors - log but don't fail the import
        import warnings
        warnings.warn(
            f"Failed to automatically set up src path: {e}. "
            f"You may need to call setup_src_path() manually or set TEST_UTILS_AUTO_SETUP=0 "
            f"to disable automatic setup.",
            ImportWarning
        )

# Perform automatic setup
_auto_setup_src_path()
```

### 2. Environment Variable Control

Added `TEST_UTILS_AUTO_SETUP` environment variable to control automatic setup:

- **Default**: `'1'` (enabled)
- **Disable**: Set to `'0'`, `'false'`, `'no'`, or `'off'`

## Key Improvements

### 1. Graceful Error Handling

**FileNotFoundError Handling:**
- Catches when src directory doesn't exist
- Silently continues (not an error in many contexts)
- Allows module to be used where src isn't available

**General Exception Handling:**
- Catches unexpected errors during setup
- Issues warning instead of failing import
- Provides helpful guidance for manual resolution

### 2. Optional Control via Environment Variable

**Environment Variable: `TEST_UTILS_AUTO_SETUP`**
- Allows disabling automatic setup when not needed
- Useful for environments where src path setup isn't required
- Prevents side effects in contexts where they're unwanted

### 3. Better User Experience

**Helpful Warning Messages:**
- Clear explanation when setup fails
- Guidance on manual setup or disabling auto-setup
- Uses `ImportWarning` category for appropriate filtering

**Graceful Degradation:**
- Module remains usable even if auto-setup fails
- Users can manually call `setup_src_path()` if needed
- No breaking changes to existing functionality

## Usage Examples

### Normal Usage (Default Behavior)
```python
# Just import - auto-setup happens automatically
from test_utils import setup_src_path, is_module_available

# src path is already set up (if src directory exists)
```

### Disable Auto-Setup
```bash
# Set environment variable to disable
export TEST_UTILS_AUTO_SETUP=0

# Or in Python
import os
os.environ['TEST_UTILS_AUTO_SETUP'] = '0'

# Then import (no auto-setup will occur)
from test_utils import setup_src_path
```

### Manual Setup When Auto-Setup is Disabled
```python
import os
os.environ['TEST_UTILS_AUTO_SETUP'] = '0'

from test_utils import setup_src_path

# Manually set up when needed
setup_src_path()
```

### Handle Missing src Directory
```python
# In environments where src might not exist
from test_utils import setup_src_path, is_module_available

# Auto-setup will fail gracefully if src doesn't exist
# Module is still usable for other functions
```

## Benefits Achieved

### 1. Prevents Import Failures
- **Problem**: Missing src directory caused import to fail
- **Solution**: Error handling allows import to succeed
- **Result**: Module usable in more contexts

### 2. Provides Control
- **Problem**: Automatic setup had side effects
- **Solution**: Environment variable allows disabling
- **Result**: Users can control when setup occurs

### 3. Better Error Messages
- **Problem**: Cryptic errors when setup failed
- **Solution**: Clear warnings with guidance
- **Result**: Easier troubleshooting and resolution

### 4. Maintains Compatibility
- **Problem**: Changes could break existing code
- **Solution**: Default behavior unchanged
- **Result**: Existing code continues to work

## Testing Scenarios

### 1. Normal Operation
- ✅ src directory exists
- ✅ Auto-setup works correctly
- ✅ Module imports successfully

### 2. Missing src Directory
- ✅ src directory doesn't exist
- ✅ Import succeeds with graceful handling
- ✅ No error thrown, module remains usable

### 3. Environment Variable Control
- ✅ `TEST_UTILS_AUTO_SETUP=0` disables auto-setup
- ✅ Module imports without attempting setup
- ✅ Manual setup still available

### 4. Error Conditions
- ✅ Unexpected errors issue warnings
- ✅ Import doesn't fail
- ✅ Helpful guidance provided

## Environment Variable Values

| Value | Effect |
|-------|--------|
| `'1'` (default) | Enable auto-setup |
| `'0'` | Disable auto-setup |
| `'false'` | Disable auto-setup |
| `'no'` | Disable auto-setup |
| `'off'` | Disable auto-setup |

## Migration Guide

### For Existing Code
No changes needed - default behavior is preserved.

### For New Code in Special Contexts
```python
# If you don't want auto-setup side effects
import os
os.environ['TEST_UTILS_AUTO_SETUP'] = '0'
from test_utils import setup_src_path

# Manually control when setup occurs
if some_condition:
    setup_src_path()
```

### For CI/CD Environments
```bash
# In environments where src structure varies
export TEST_UTILS_AUTO_SETUP=0

# Or allow auto-setup with graceful handling (default)
# No environment variable needed
```

## Impact

### Reliability
- Module works in more environments
- Graceful handling of missing directories
- Better error recovery

### Flexibility
- Optional control over automatic behavior
- Suitable for various deployment contexts
- Maintains backward compatibility

### User Experience
- Clear error messages and guidance
- No breaking changes
- Easy to control and customize

This improvement makes the test utilities more robust and flexible while maintaining full backward compatibility and providing better error handling for edge cases.