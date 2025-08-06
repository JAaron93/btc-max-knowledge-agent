from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, Tuple
import random
import time

DEFAULT_INITIAL_DELAY: float = 0.1
DEFAULT_FACTOR: float = 2.0
DEFAULT_MULTIPLIER: float = DEFAULT_FACTOR
DEFAULT_MAX_DELAY: float = 5.0
DEFAULT_MAX_RETRIES: int = 5
DEFAULT_JITTER: float = 0.1  # 10% jitter

@dataclass
class BackoffConfig:
    initial_delay: float = DEFAULT_INITIAL_DELAY
    factor: float = DEFAULT_FACTOR
    max_delay: float = DEFAULT_MAX_DELAY
    max_retries: int = DEFAULT_MAX_RETRIES
    jitter: float = DEFAULT_JITTER  # proportion of delay to add/subtract

def _apply_jitter(delay: float, jitter: float) -> float:
    if jitter <= 0:
        return delay
    delta = delay * jitter
    return max(0.0, delay + random.uniform(-delta, delta))

def backoff_sequence(config: Optional[BackoffConfig] = None) -> Iterator[float]:
    cfg = config or BackoffConfig()
    delay = cfg.initial_delay
    for _ in range(cfg.max_retries):
        yield min(delay, cfg.max_delay)
        delay = min(delay * cfg.factor, cfg.max_delay)

def next_backoff(state: Optional[Tuple[int, float]] = None, config: Optional[BackoffConfig] = None) -> Tuple[Tuple[int, float], float, bool]:
    """Return (new_state, sleep_time, should_continue). State is (attempt, last_delay)."""
    cfg = config or BackoffConfig()
    attempt, last = state if state is not None else (0, 0.0)
    if attempt >= cfg.max_retries:
        return (attempt, last), 0.0, False
    delay = cfg.initial_delay if attempt == 0 else min(last * cfg.factor, cfg.max_delay)
    delay = min(delay, cfg.max_delay)
    jittered = _apply_jitter(delay, cfg.jitter)
    return (attempt + 1, delay), jittered, True

__all__ = [
    'DEFAULT_INITIAL_DELAY','DEFAULT_FACTOR','DEFAULT_MAX_DELAY','DEFAULT_MAX_RETRIES','DEFAULT_JITTER',
    'BackoffConfig','backoff_sequence','next_backoff'
]


def reset_backoff():
    """Stateless helper for API parity. Present for compatibility; no-op."""
    return None


def total_backoff_time(retries: int, initial: float = None, factor: float = None, max_delay: float = None) -> float:
    """Compute total wait time for given retries using configured defaults."""
    init = initial if initial is not None else (DEFAULT_INITIAL_DELAY if 'DEFAULT_INITIAL_DELAY' in globals() else 0.1)
    fac = factor if factor is not None else (DEFAULT_FACTOR if 'DEFAULT_FACTOR' in globals() else 2.0)
    mx = max_delay if max_delay is not None else (DEFAULT_MAX_DELAY if 'DEFAULT_MAX_DELAY' in globals() else float('inf'))
    total = 0.0
    delay = init
    for _ in range(max(0, retries)):
        total += min(delay, mx)
        delay = min(delay * fac, mx)
    return total
