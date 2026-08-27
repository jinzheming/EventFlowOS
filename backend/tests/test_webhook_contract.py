"""P9b contract tests: webhook signature and outbox status derivation.

No database required — these exercise pure helpers only.
"""
import hashlib
import hmac
import socket

import pytest

import personal_affairs.application.webhook_urls as webhook_urls
from personal_affairs.api.routes.webhooks import _event_status
from personal_affairs.application.webhook_urls import WebhookUrlError, validate_webhook_url
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


def test_validate_webhook_url_normalizes_public_destination(monkeypatch) -> None:
    def fake_getaddrinfo(host: str, port: int, type: int = 0) -> list[tuple]:
        assert host == "example.com"
        assert port == 443
        assert type == socket.SOCK_STREAM
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", port))]

    monkeypatch.setattr(webhook_urls, "getaddrinfo", fake_getaddrinfo)

    assert validate_webhook_url(" HTTPS://Example.com/hook?q=1 ") == "https://example.com/hook?q=1"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/hook",
        "https://user:pass@example.com/hook",
        "https://example.com/hook#fragment",
        "https://example.com:99999/hook",
    ],
)
def test_validate_webhook_url_rejects_unsafe_shape(url: str) -> None:
    with pytest.raises(WebhookUrlError):
        validate_webhook_url(url, allow_private=True)


def test_validate_webhook_url_rejects_private_destination(monkeypatch) -> None:
    def fake_getaddrinfo(host: str, port: int, type: int = 0) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", port))]

    monkeypatch.setattr(webhook_urls, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(WebhookUrlError):
        validate_webhook_url("https://example.com/hook")


def test_validate_webhook_url_enforces_allowed_hosts(monkeypatch) -> None:
    def fake_getaddrinfo(host: str, port: int, type: int = 0) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", port))]

    monkeypatch.setattr(webhook_urls, "getaddrinfo", fake_getaddrinfo)

    assert validate_webhook_url("https://hooks.example.com/a", allowed_hosts="*.example.com")
    assert validate_webhook_url("https://example.com/a", allowed_hosts=".example.com")
    with pytest.raises(WebhookUrlError):
        validate_webhook_url("https://attacker.test/a", allowed_hosts=".example.com")
