from starlette.datastructures import Headers
from starlette.requests import Request

from personal_affairs.api.routes.auth import secure_session_cookie


def request_for_scheme(scheme: str, headers: dict[str, str] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "scheme": scheme,
            "method": "GET",
            "path": "/",
            "server": ("tasks.example.com", 443),
            "headers": Headers(headers or {}).raw,
        }
    )


def test_session_cookie_is_not_secure_on_http_tailnet_entry() -> None:
    assert secure_session_cookie(request_for_scheme("http")) is False


def test_session_cookie_is_secure_on_https_entry() -> None:
    assert secure_session_cookie(request_for_scheme("https")) is True


def test_session_cookie_honors_forwarded_https_proto() -> None:
    assert secure_session_cookie(request_for_scheme("http", {"x-forwarded-proto": "https"})) is True
