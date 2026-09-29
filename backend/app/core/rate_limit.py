import time
from collections import defaultdict

_attempts: dict[str, list[float]] = defaultdict(list)


def is_rate_limited(key: str, *, max_attempts: int, window_seconds: int) -> bool:
    now = time.monotonic()
    window_start = now - window_seconds
    recent = [attempt for attempt in _attempts[key] if attempt > window_start]
    _attempts[key] = recent
    return len(recent) >= max_attempts


def record_attempt(key: str) -> None:
    _attempts[key].append(time.monotonic())
