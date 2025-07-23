"""
Tests package for BTC Max Knowledge Agent.

This package contains all the test modules for the project.
"""

# Make test modules available for import
import os
import sys

# Add the project root to the Python path only if not already present
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
