import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def parse_env_file(
    path: Path | str, *, allow_override: bool = False, prefix: str | None = None
) -> dict[str, str]:
    """
    Reads KEY=VALUE pairs from a .env file, skipping blanks/comments.

    Args:
        path: The path to the .env file.
        allow_override: If True, allows overriding existing environment variables.
        prefix: If provided, only processes keys starting with this prefix.

    Returns:
        A dict of the keys that were newly set or overridden.
    """
    env_vars: dict[str, str] = {}
    path = Path(path)

    if not path.is_file():
        log.warning(f"Env file not found at: {path}")
        return env_vars

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            log.warning(f"Skipping invalid line in {path}: {line}")
            continue

        key, value = line.split("=", 1)
        key = key.strip()

        if prefix and not key.startswith(prefix):
            continue

        if key in os.environ:
            if allow_override:
                log.warning(f"Overriding existing environment variable: {key}")
                os.environ[key] = value
                env_vars[key] = value
            else:
                log.warning(f"Skipping environment variable that already exists: {key}")
        else:
            os.environ[key] = value
            env_vars[key] = value

    return env_vars
