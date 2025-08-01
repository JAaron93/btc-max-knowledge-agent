# Test Utils Environment Variables

## TEST_UTILS_AUTO_SETUP

Controls whether `test_utils.py` automatically sets up the src path on import.

### Values

**Truthy values (enable automatic setup):**
- **`1`** (default): Enable automatic setup
- **`true`**, **`True`**, **`TRUE`**: Enable automatic setup
- **`yes`**, **`Yes`**, **`YES`**: Enable automatic setup  
- **`on`**, **`On`**, **`ON`**: Enable automatic setup
- Any other value not listed below

**Falsy values (disable automatic setup):**
- **`0`**: Disable automatic setup  
- **`false`**, **`False`**, **`FALSE`**: Disable automatic setup
- **`no`**, **`No`**, **`NO`**: Disable automatic setup
- **`off`**, **`Off`**, **`OFF`**: Disable automatic setup

**Note:** Value comparison is case-insensitive. Any value not in the falsy list is treated as enabled.

### Usage

#### Enable (Default)
```bash
# No environment variable needed (default behavior)
# Or explicitly enable:
export TEST_UTILS_AUTO_SETUP=1
```

#### Disable
```bash
export TEST_UTILS_AUTO_SETUP=0
```

#### In Python
```python
import os
os.environ['TEST_UTILS_AUTO_SETUP'] = '0'  # Disable
# Must be set before importing test_utils
from test_utils import setup_src_path

# Call manually when needed
setup_src_path()
```

### When to Disable

- **CI/CD environments** where src structure varies
- **Packaging contexts** where src path isn't needed
- **Testing environments** where you want to control setup timing
- **Library usage** where side effects should be minimized

### Manual Setup When Disabled

```python
import os
os.environ['TEST_UTILS_AUTO_SETUP'] = '0'

from test_utils import setup_src_path

# Call manually when needed
setup_src_path()
```