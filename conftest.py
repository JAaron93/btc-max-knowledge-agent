"""Root conftest.py to configure Python path and test environment."""

import os
import sys
from pathlib import Path

# Add src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"

# Insert paths at the beginning to ensure priority
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Also add project root for direct imports
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set PYTHONPATH environment variable as well
current_pythonpath = os.environ.get("PYTHONPATH", "")
paths_to_add = [str(src_path), str(project_root)]  # src_path first for priority

for path in paths_to_add:
    if path not in current_pythonpath:
        if current_pythonpath:
            current_pythonpath = f"{path}{os.pathsep}{current_pythonpath}"
        else:
            current_pythonpath = path

os.environ["PYTHONPATH"] = current_pythonpath

# Also ensure any future module imports can work by creating
# manual module registrations for critical paths
# Note: We don't pre-import here to avoid module state conflicts
