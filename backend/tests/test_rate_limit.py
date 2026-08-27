import pytest

from personal_affairs.api.rate_limit import (
    InMemoryRateLimiter,
    enforce_rate_limit,
    limiter,
    rate_limit_key_part,
)
from personal_affairs.config import Settings
from personal_affairs.domain.errors import DomainError, ErrorCode


def test_in_memory_rate_limiter_blocks_until_window_expires() -> None:
    rate_limiter = InMemoryRateLimiter()

    assert rate_limiter.check("login:client", 2, 10, now=0.0) == (True, 0)
    assert rate_limiter.check("login:client", 2, 10, now=1.0) == (True, 0)

    allowed, retry_after = rate_limiter.check("login:client", 2, 10, now=2.0)
    assert allowed is False
    assert retry_after == 8

    assert rate_limiter.check("login:client", 2, 10, now=10.1) == (True, 0)


def test_rate_limit_key_part_normalizes_and_bounds_values() -> None:
    assert rate_limit_key_part("  User\nName  ") == "user name"
    assert len(rate_limit_key_part("x" * 300)) == 200


def test_enforce_rate_limit_raises_domain_error() -> None:
    limiter.reset()
    cfg = Settings(rate_limit_window_seconds=60)

    enforce_rate_limit(cfg, "login", "client", 1)
    with pytest.raises(DomainError) as exc_info:
        enforce_rate_limit(cfg, "login", "client", 1)

    assert exc_info.value.code == ErrorCode.RATE_LIMITED
    assert exc_info.value.http_status == 429
    assert exc_info.value.retryable is True
    limiter.reset()
