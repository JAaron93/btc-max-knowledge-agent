# Lightweight utils package initializer to avoid importing src/__init__.py side effects during tests.
# Expose legacy modules explicitly without triggering btc_max_knowledge_agent namespacing resolution.
try:
    from .audio_utils import *  # noqa: F401,F403
except Exception:
    pass
try:
    from .exponential_backoff import *  # noqa: F401,F403
except Exception:
    pass
try:
    from .url_error_handler import *  # noqa: F401,F403
except Exception:
    pass
try:
    from .url_metadata_logger import *  # noqa: F401,F403
except Exception:
    pass
