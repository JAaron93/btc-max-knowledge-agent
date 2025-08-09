# Import Refactoring Guide: Removing sys.path Manipulation

## Issue
Many scripts in the project use runtime `sys.path` manipulation to import modules:

```python
# Problematic approach
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from src.utils.module import SomeClass
```

## Solution
Since the project is properly configured as an installable package and is already installed in development mode (`pip install -e .`), we can use proper package imports instead.

## Package Structure
The project is configured in `pyproject.toml` as:
- **Package name**: `btc_max_knowledge_agent`
- **Source location**: `src/`
- **Installation**: Development mode (`pip install -e .`)

## Refactoring Examples

### ✅ Fixed: scripts/clean_mcp_response.py

**Before:**
```python
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.utils.result_formatter import MCPResponseFormatter
except ImportError:
    MCPResponseFormatter = None
```

**After:**
```python
try:
    from btc_max_knowledge_agent.utils.result_formatter import MCPResponseFormatter
except ImportError:
    # Fallback if import fails or package not installed
    MCPResponseFormatter = None
```

### 🔧 Other Files Needing Refactoring

#### Scripts Directory
- `scripts/validate_integration.py`
- `scripts/type_safety_improvement_demo.py`

#### Examples Directory
- `examples/demo_tts_ui.py`
- `examples/session_management_demo.py`
- `examples/demo_pinecone_assistant_url_metadata.py`
- `examples/secure_prompt_processing_demo.py`
- And many others...

## Import Mapping Guide

## Import Mapping Guide

### Mapping Guidelines
1. Identify the original `sys.path` manipulation block.
2. Determine the corresponding package import path based on the project name `btc_max_knowledge_agent`.
3. Replace the manipulation with a standard absolute import using the package name.
4. Add a fallback `try/except ImportError` block if the script may be executed in environments where the package is not installed.
5. Run the test suite to ensure imports resolve correctly.

**Example Mapping**

```python
# Before
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from src.utils.module import SomeClass
```

```python
# After
try:
    from btc_max_knowledge_agent.utils.module import SomeClass
except ImportError:
    # Fallback for direct script execution
    from src.utils.module import SomeClass
```

Follow these steps for each script listed under **Other Files Needing Refactoring**.
## Cleaned Up Section

The following sections have been removed because they contained corrupted text that did not provide useful guidance. Below is a concise summary of the remaining actionable items for the import refactoring guide:

### Next Steps for Developers
1. **Verify Refactoring** – Ensure all scripts listed under **Other Files Needing Refactoring** have been updated to use the package import pattern demonstrated in the **Import Mapping Guide**.
2. **Run Test Suite** – Execute the project's test suite to confirm that the new imports resolve correctly and that no runtime errors are introduced.
3. **Update Documentation** – Keep this guide up‑to‑date with any new scripts that require refactoring.
4. **Continuous Integration** – Add a CI check that fails if `sys.path` manipulation is detected in the codebase (e.g., using a simple grep or lint rule).

### Recommended: Console Scripts Entry Points

For CLI scripts that need to be distributed or run reliably across environments, consider using `console_scripts` entry points in `pyproject.toml` instead of direct script execution with import hacks.

**Benefits:**
- ✅ **No sys.path manipulation**: Entry points handle import paths automatically
- ✅ **Cross-platform compatibility**: Works consistently across different operating systems
- ✅ **Virtual environment friendly**: Automatically available when package is installed
- ✅ **Professional distribution**: Standard approach for Python CLI tools

**Implementation Example:**
```toml
[project.scripts]
btc-assistant = "btc_max_knowledge_agent.cli.assistant:main"
btc-setup = "btc_max_knowledge_agent.cli.setup:main"
btc-verify = "btc_max_knowledge_agent.cli.verify:main"
```

**Migration Steps:**
1. Move CLI logic from `scripts/` to proper modules under `src/btc_max_knowledge_agent/cli/`
2. Define entry points in `pyproject.toml`
3. Remove `sys.path` manipulation and fragile import fallbacks
4. Test with `pip install -e .` to verify entry points work correctly

This approach eliminates the need for import hacks and provides a more maintainable, professional CLI interface.

### Reference Checklist
- [ ] All `sys.path` insertions removed.
- [ ] Package imports use `btc_max_knowledge_agent` namespace.
- [ ] Fallback `try/except ImportError` blocks retained where needed.
- [ ] Tests pass without import errors.

Feel free to expand this section with additional details or examples as the project evolves.
