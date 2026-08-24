"""P9b contract tests: webhook signature and outbox status derivation.

No database required — these exercise pure helpers only.
"""
import hashlib
import hmac

import pytest

from personal_affairs.api.routes.webhooks import _event_status
from personal_affairs.workers.webhook_worker import sign_payload


def test_sign_payload_hmac_sha256() -> None:
    body = b'{"event_type":"item.completed"}'
    signature = sign_payload("s3cret", body)
    expected = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert signature == expected
    assert signature != sign_payload("other-secret", body)
    assert signature != sign_payload("s3cret", b"different")


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"published_at": "2026-08-23T00:00:00Z", "last_error_code": None, "claimed_at": None}, "published"),
        ({"published_at": None, "last_error_code": "DEAD:HTTP_500", "claimed_at": None}, "dead"),
        ({"published_at": None, "last_error_code": None, "claimed_at": "2026-08-23T00:00:00Z"}, "delivering"),
        ({"published_at": None, "last_error_code": "HTTP_500", "claimed_at": None}, "retrying"),
        ({"published_at": None, "last_error_code": None, "claimed_at": None}, "pending"),
    ],
)
def test_event_status(row: dict, expected: str) -> None:
    assert _event_status(row) == expected
