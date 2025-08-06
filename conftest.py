"""
Minimal root conftest.py.

Intentionally left minimal to avoid duplicating path/env mutations.
- Import path handling is configured via pytest.ini (pythonpath = src)
- Test-specific fixtures, CWD normalization, env defaults, and shims
  live in tests/conftest.py

Rationale:
Keeping this file minimal prevents import-precedence ambiguity and
environment drift between local and CI runs.
"""
