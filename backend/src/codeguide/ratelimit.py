"""A small in-process sliding-window rate limiter.

Per-process (not shared across replicas) — documented as a scaling caveat in
the threat model. Adequate for protecting the sandbox pool and the enrolment
endpoint against a single abusive client.
"""

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        now = time.monotonic()
        events = self._events[key]
        while events and events[0] < now - window_s:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        # Bound memory: drop empty deques for keys that have aged out.
        if not events:
            self._events.pop(key, None)
        return True
