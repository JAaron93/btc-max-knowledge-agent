"""
Global pytest configuration and fixtures for the hybrid test layout.

This conftest centralizes:
- Path helpers for test data across all suites
  (unit / integration / e2e / performance / ui / security)
- CWD normalization to repository root
- Optional sys.path augmentation for 'src' to import project packages
- Asyncio/anyio settings aligned with pytest.ini plugins
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator, Optional, Callable, Iterable
from typing import Final, Any

import pytest


# --------------------------------------------------------------------------------------
# Repository and paths
# --------------------------------------------------------------------------------------

def _repo_root() -> Path:
    # tests/ is configured as testpaths; conftest resides in tests/
    return Path(__file__).resolve().parent.parent


def _src_root() -> Path:
    return _repo_root() / "src"


def _tests_root() -> Path:
    return _repo_root() / "tests"


# Ensure 'src' is on sys.path for import-time safety without editable installs
_src = _src_root()
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


# --------------------------------------------------------------------------------------
# CWD normalization
# --------------------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _normalize_cwd_session() -> Generator[None, None, None]:
    """
    Normalize the working directory for the test session to the repo root.
    Some tests assume relative file access from project root.
    """
    original_cwd = Path.cwd()
    os.chdir(_repo_root())
    try:
        yield
    finally:
        os.chdir(original_cwd)


# --------------------------------------------------------------------------------------
# Test data path helper
# --------------------------------------------------------------------------------------

@pytest.fixture(scope="session")
def repo_root() -> Path:
    """
    Path to the repository root directory.
    """
    return _repo_root()


@pytest.fixture(scope="session")
def tests_root() -> Path:
    """
    Path to tests/ root directory.
    """
    return _tests_root()


@pytest.fixture(scope="session")
def src_root() -> Path:
    """
    Path to src/ root directory.
    """
    return _src_root()


@pytest.fixture(scope="session")
def resolve_test_path(tests_root: Path) -> Callable[[str], Path]:
    """
    Resolve a relative path within tests/ to an absolute Path.
    Use for shared test assets irrespective of suite (unit/integration/e2e).

    Example:
        p = resolve_test_path("fixtures/sample.json")
    """
    def _resolver(rel_path: str) -> Path:
        return (tests_root / rel_path).resolve()

    return _resolver


# --------------------------------------------------------------------------------------
# Legacy parameterization helpers expected by some tests
# --------------------------------------------------------------------------------------
# Avoid callable names starting with 'pytest_' to prevent pluggy
# treating them as hooks. Expose constants and normal fixtures,
# plus legacy-named variables.

CONFIG_VARIANTS: Final[tuple[tuple[str, dict[str, Any]], ...]] = (
    ("default-config0", {"truncation_length": 100, "mode": "default"}),
    ("custom-config1", {"truncation_length": 50, "mode": "custom"}),
    ("short-config2", {"truncation_length": 25, "mode": "short"}),
    ("extended-config3", {"truncation_length": 200, "mode": "extended"}),
)

TRUNCATION_LENGTHS: Final[tuple[int, ...]] = (25, 50, 100, 200, 500)

@pytest.fixture(scope="session")
def config_variants() -> Iterable[tuple[str, dict[str, Any]]]:
    """Preferred fixture to access config variants."""
    return CONFIG_VARIANTS



@pytest.fixture(scope="session")
def truncation_lengths() -> Iterable[int]:
    """Preferred fixture to access truncation lengths."""
    return TRUNCATION_LENGTHS


# Back-compat variables for imports like:
#   from tests.conftest import pytest_parametrize_*
# IMPORTANT: Do NOT define callables whose names start with 'pytest_'.
# Pluggy treats them as hooks, causing PluginValidationError.
# We only expose DATA variables here, and a separate decorator with a
# safe name.

pytest_parametrize_config_variants = CONFIG_VARIANTS  # type: ignore[N816]
pytest_parametrize_truncation_lengths = TRUNCATION_LENGTHS

# Safe decorator alias for legacy usage expecting a decorator behavior.
# Use as:
#   from tests.conftest import parametrize_truncation_lengths
#   @parametrize_truncation_lengths
#   def test_...(truncation_length): ...
def parametrize_truncation_lengths(func: "Callable") -> "Callable":
    return pytest.mark.parametrize(
        "truncation_length", TRUNCATION_LENGTHS
    )(func)


# --------------------------------------------------------------------------------------
# Environment stability for tests
# --------------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _stable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Provide default environment values for tests while allowing overrides.
    Only sets values if not already present to avoid masking explicit configs.
    """
    defaults = {
        "PYTHONHASHSEED": "0",
        # Ensure optional salts/keys used in security tests have
        # deterministic defaults
        "TEST_ADMIN_HASH_SALT": "tests-default-salt",
        # Placeholders for network-sensitive tests which should be mocked
        "BTC_MAX_KNOWLEDGE_AGENT_ENV": "test",
    }
    for key, val in defaults.items():
        if os.environ.get(key) is None:
            monkeypatch.setenv(key, val)


# --------------------------------------------------------------------------------------
# Asyncio/AnyIO alignment
# --------------------------------------------------------------------------------------
# The project uses pytest-asyncio with STRICT mode declared in pytest.ini.
# If legacy tests rely on default loop scope, they can use these fixtures.


@pytest.fixture(scope="session")
def event_loop_policy() -> Optional[str]:
    """
    Hook to declare a custom event loop policy name if needed in the future.
    Returning None keeps the default.
    """
    return None


# --------------------------------------------------------------------------------------
# Backward-compatibility import shims for legacy test imports (optional)
# --------------------------------------------------------------------------------------

def _install_legacy_test_import_shims() -> None:
    """
    If legacy tests import modules by old names or expect importable
    test packages,
    set up minimal namespace shims here. Keep this light and import-safe.
    Currently, we avoid explicit shims; add as needed if regressions are found.
    """
    # Example placeholder:
    # import types
    # legacy = types.ModuleType("legacy_tests_utils")
    # legacy.some_helper = new_location.some_helper
    # sys.modules["legacy_tests_utils"] = legacy
    return


_install_legacy_test_import_shims()