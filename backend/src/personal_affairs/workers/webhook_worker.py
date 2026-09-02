"""P9b: webhook publisher.

Claims due events from the outbox (lease semantics mirrored from the reminder
worker), delivers each to every matching active subscription with an HMAC
signature, retries with backoff, and drops to dead after the attempt cap.
"""
import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from socket import gethostname
from uuid import UUID

import httpx

from personal_affairs.application.webhook_urls import (
    WebhookUrlError,
    validate_webhook_redirect,
    validate_webhook_url,
)
from personal_affairs.config import Settings, get_settings
from personal_affairs.domain.reminder_state import next_retry_at
from personal_affairs.storage.database import connection
from personal_affairs.storage.repositories.event_outbox import EventOutboxRepository
from personal_affairs.storage.repositories.webhooks import WebhookSubscriptionsRepository


def _worker_id() -> str:
    return f"webhook:{gethostname()}:{id(object())}"


def sign_payload(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _event_body(event: dict) -> bytes:
    body = {
        "event_type": event["event_type"],
        "aggregate": event["aggregate"],
        "aggregate_id": str(event["aggregate_id"]),
        "payload": event["payload"],
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    return json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")


async def _read_limited_response_text(response: httpx.Response, limit_bytes: int) -> str:
    chunks: list[bytes] = []
    total = 0
    truncated = False
    limit = max(0, limit_bytes)
    async for chunk in response.aiter_bytes():
        if total + len(chunk) > limit:
            truncated = True
        if total < limit:
            chunks.append(chunk[: limit - total])
        total += len(chunk)
        if total >= limit:
            break
    text = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    return f"{text} [truncated]" if truncated else text


async def _deliver(
    sub: dict,
    event: dict,
    cfg: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bool, str, str]:
    try:
        url = validate_webhook_url(
            sub["url"],
            allow_private=cfg.webhook_allow_private_urls,
            allowed_hosts=cfg.webhook_allowed_hosts,
        )
    except WebhookUrlError as exc:
        return False, "INVALID_WEBHOOK_URL", str(exc)[:200]

    body = _event_body(event)
    headers = {
        "Content-Type": "application/json",
        "X-PA-Event-Id": str(event["id"]),
        "X-PA-Event-Type": event["event_type"],
        "X-PA-Retry-Count": str(event["attempt_count"]),
        "X-PA-Signature": sign_payload(sub["secret"], body),
    }
    client_kwargs = {"timeout": cfg.webhook_timeout_seconds, "follow_redirects": False}
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        async with httpx.AsyncClient(**client_kwargs) as client, client.stream(
            "POST", url, content=body, headers=headers
        ) as response:
            if 200 <= response.status_code < 300:
                return True, "OK", ""
            if 300 <= response.status_code < 400:
                try:
                    validate_webhook_redirect(
                        url,
                        response.headers.get("location"),
                        allow_private=cfg.webhook_allow_private_urls,
                        allowed_hosts=cfg.webhook_allowed_hosts,
                    )
                except WebhookUrlError as exc:
                    return False, "REDIRECT_BLOCKED", str(exc)[:200]
                return False, "REDIRECT_BLOCKED", "Webhook redirects are not followed."
            message = await _read_limited_response_text(
                response,
                cfg.webhook_response_body_limit_bytes,
            )
        return False, f"HTTP_{response.status_code}", (message or response.reason_phrase)[:200]
    except Exception as exc:
        return False, "NETWORK_ERROR", str(exc)[:200]


async def publish_once(worker_id: str) -> int:
    cfg = get_settings()
    with connection(cfg) as conn:
        repo = EventOutboxRepository(conn)
        repo.recover_expired_leases(cfg.webhook_lease_seconds)
        events = repo.claim_batch(worker_id, cfg.webhook_lease_seconds, cfg.webhook_batch_size)
        repo.record_webhook_heartbeat(worker_id, claimed_count=len(events))
        conn.commit()
    for event in events:
        await _publish_event(worker_id, event, cfg)
    return len(events)


async def _publish_event(worker_id: str, event: dict, cfg) -> None:
    user_id = event["user_id"]
    with connection(cfg) as conn:
        subs = WebhookSubscriptionsRepository(conn).list_active_for_event(user_id, event["event_type"])
    if not subs:
        with connection(cfg) as conn:
            repo = EventOutboxRepository(conn)
            repo.mark_published(event["id"])
            repo.record_webhook_heartbeat(worker_id, published_count=1)
            conn.commit()
        return

    failures: list[tuple[str, str]] = []
    for sub in subs:
        ok, code, message = await _deliver(sub, event, cfg)
        if not ok:
            failures.append((code, message))

    with connection(cfg) as conn:
        repo = EventOutboxRepository(conn)
        if not failures:
            repo.mark_published(event["id"])
            repo.record_webhook_heartbeat(worker_id, published_count=1)
        else:
            attempt = int(event["attempt_count"])
            seed = int(UUID(str(event["id"])).int % 999999)
            retry_at = next_retry_at(attempt, datetime.now(UTC), seed)
            code = ",".join(sorted({f[0] for f in failures}))
            message = "; ".join(f[1] for f in failures[:2]) or code
            if retry_at is None:
                code = "DEAD:" + code
            repo.mark_failure(event["id"], attempt, retry_at, code, message)
            repo.record_webhook_heartbeat(worker_id, failed_count=1)
        conn.commit()


async def run_forever() -> None:
    cfg = get_settings()
    worker_id = _worker_id()
    while True:
        await publish_once(worker_id)
        await asyncio.sleep(cfg.webhook_poll_seconds)


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
