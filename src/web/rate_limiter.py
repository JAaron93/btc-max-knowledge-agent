from typing import Dict

class RateLimiter:
    def __init__(self, limit: int = 10) -> None:
        self.limit = limit
        self._count: Dict[str, int] = {}
    def allow(self, key: str) -> bool:
        c = self._count.get(key, 0)
        if c >= self.limit:
            return False
        self._count[key] = c + 1
        return True
    def stats(self) -> Dict[str, int]:
        return dict(self._count)

class SessionRateLimiter(RateLimiter):
    pass

_singleton_session_rl: SessionRateLimiter | None = None

def get_session_rate_limiter(limit: int = 10) -> SessionRateLimiter:
    global _singleton_session_rl
    if _singleton_session_rl is None:
        _singleton_session_rl = SessionRateLimiter(limit=limit)
    return _singleton_session_rl
