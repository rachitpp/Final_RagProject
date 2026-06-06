# =============================================================
# Minimal in-memory sliding-window rate limiter for the auth endpoints.
#
# Scope / honesty about limits: this is process-local state. It throttles
# brute-force against a single backend process (the demo deployment) and resets
# on restart. It is NOT a substitute for a real limiter — for multi-process or
# public exposure, do this at the edge (nginx/Cloudflare) or with a shared store
# (Redis). bcrypt already slows each guess; this caps how many guesses land.
#
# Client IP comes from request.client.host. We deliberately do NOT trust
# X-Forwarded-For (spoofable unless you have a proxy you control stripping/setting
# it); add that handling when you deploy behind such a proxy.
# =============================================================
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from config.settings import settings


def client_ip(request: Request) -> str:
    """Best-effort client IP for keying the limiter."""
    return request.client.host if request.client else "unknown"


class SlidingWindowLimiter:
    """Allow at most `max_attempts` hits per `window_seconds` for a given key."""

    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Record an attempt for `key`; raise 429 if it exceeds the window budget.

        A blocked request is NOT recorded, so hammering while blocked doesn't
        keep extending the window — the client just waits for the oldest hit to
        age out.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.max_attempts:
                retry_after = int(hits[0] + self.window_seconds - now) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please wait a moment and try again.",
                    headers={"Retry-After": str(max(retry_after, 1))},
                )
            hits.append(now)
            # Note: idle keys keep an empty deque until next touched. Bounded by
            # the number of distinct (IP, employee_id) pairs — negligible for an
            # internal tool. Add a periodic sweep if that ever stops being true.

    def reset(self) -> None:
        """Clear all recorded attempts (used to isolate tests)."""
        with self._lock:
            self._hits.clear()


# Process-wide limiter shared by the auth routes.
login_limiter = SlidingWindowLimiter(
    max_attempts=settings.login_rate_max_attempts,
    window_seconds=settings.login_rate_window_seconds,
)
