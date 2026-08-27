from __future__ import annotations

from collections import deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import Request

from personal_affairs.config import Settings
from personal_affairs.domain.errors import DomainError, ErrorCode


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        *,
        now: float | None = None,
    ) -> tuple[bool, int]:
        if limit <= 0 or window_seconds <= 0:
            return True, 0
        current = monotonic() if now is None else now
        cutoff = current - window_seconds
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, ceil(window_seconds - (current - bucket[0])))
                return False, retry_after
            bucket.append(current)
        return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = InMemoryRateLimiter()


def client_host(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit_key_part(value: object) -> str:
    cleaned = " ".join(str(value).strip().lower().split())
    return cleaned[:200] or "unknown"


def enforce_rate_limit(cfg: Settings, action: str, key: str, limit: int) -> None:
    if not cfg.rate_limit_enabled:
        return
    allowed, retry_after = limiter.check(
        f"{action}:{key}",
        limit,
        cfg.rate_limit_window_seconds,
    )
    if allowed:
        return
    raise DomainError(
        ErrorCode.RATE_LIMITED,
        f"Too many {action.replace('_', ' ')} requests. Retry after {retry_after} seconds.",
        429,
        retryable=True,
    )
