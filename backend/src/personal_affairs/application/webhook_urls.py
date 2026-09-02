from __future__ import annotations

from ipaddress import ip_address
from socket import SOCK_STREAM, getaddrinfo
from urllib.parse import urljoin, urlsplit, urlunsplit


class WebhookUrlError(ValueError):
    pass


def validate_webhook_url(raw_url: str, *, allow_private: bool = False, allowed_hosts: str = "") -> str:
    value = raw_url.strip()
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise WebhookUrlError("Webhook URL must use http or https.")
    if not parsed.hostname:
        raise WebhookUrlError("Webhook URL must include a host.")
    if parsed.username or parsed.password:
        raise WebhookUrlError("Webhook URL must not include credentials.")
    if parsed.fragment:
        raise WebhookUrlError("Webhook URL must not include a fragment.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise WebhookUrlError("Webhook URL includes an invalid port.") from exc

    host = parsed.hostname.rstrip(".").lower()
    if allowed_hosts and not _is_allowed_host(host, allowed_hosts):
        raise WebhookUrlError("Webhook URL host is not in the allowed host list.")
    if not allow_private:
        _validate_public_destination(host, port or (443 if scheme == "https" else 80))

    return urlunsplit((scheme, _netloc(host, port), parsed.path or "", parsed.query, ""))


def validate_webhook_redirect(
    source_url: str,
    location: str | None,
    *,
    allow_private: bool = False,
    allowed_hosts: str = "",
) -> str:
    if not location or not location.strip():
        raise WebhookUrlError("Webhook redirect did not include a Location header.")
    target = validate_webhook_url(
        urljoin(source_url, location.strip()),
        allow_private=allow_private,
        allowed_hosts=allowed_hosts,
    )
    if urlsplit(target).scheme != "https":
        raise WebhookUrlError("Webhook redirects must target https URLs.")
    return target


def _netloc(host: str, port: int | None) -> str:
    rendered_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    if port is None:
        return rendered_host
    return f"{rendered_host}:{port}"


def _is_allowed_host(host: str, allowed_hosts: str) -> bool:
    for entry in (part.strip().lower() for part in allowed_hosts.split(",")):
        if not entry:
            continue
        if entry.startswith("*."):
            entry = entry[1:]
        if entry.startswith(".") and (host == entry[1:] or host.endswith(entry)):
            return True
        if host == entry:
            return True
    return False


def _validate_public_destination(host: str, port: int) -> None:
    try:
        addresses = getaddrinfo(host, port, type=SOCK_STREAM)
    except OSError as exc:
        raise WebhookUrlError("Webhook URL host could not be resolved.") from exc
    if not addresses:
        raise WebhookUrlError("Webhook URL host could not be resolved.")
    for result in addresses:
        address = result[4][0]
        if not ip_address(address).is_global:
            raise WebhookUrlError("Webhook URL must resolve only to public internet addresses.")
