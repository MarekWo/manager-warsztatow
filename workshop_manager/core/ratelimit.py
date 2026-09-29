"""A small fixed-window rate limit on the shared (database) cache."""

from django.core.cache import cache


def hit(key: str, *, limit: int, window_seconds: int) -> bool:
    """Count one event under `key`; False once more than `limit` happened in the window."""
    cache_key = f"ratelimit:{key}"
    if cache.add(cache_key, 1, timeout=window_seconds):
        return True
    try:
        count = cache.incr(cache_key)
    except ValueError:  # expired between add() and incr()
        cache.add(cache_key, 1, timeout=window_seconds)
        return True
    return count <= limit
