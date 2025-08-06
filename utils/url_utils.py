from __future__ import annotations
from urllib.parse import urlparse
from typing import Iterable, List

def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return parsed.netloc or parsed.path.split("/")[0]
    except Exception:
        return ""

def sanitize_url_for_storage(url: str) -> str:
    return url.strip()

def validate_url_batch(urls: Iterable[str]) -> List[bool]:
    out = []
    for u in urls:
        d = extract_domain(u)
        out.append(bool(d))
    return out


def check_urls_accessibility_parallel(urls):
    """Simple synchronous placeholder used by tests; returns list[bool] of validity by domain presence."""
    try:
        return [bool(extract_domain(u)) for u in urls]
    except Exception:
        return [False for _ in urls]
