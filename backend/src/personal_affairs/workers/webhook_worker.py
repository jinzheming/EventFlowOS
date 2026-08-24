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

from personal_affairs.config import get_settings
from personal_affairs.domain.reminder_state import next_retry_at
from personal_affairs.storage.database import connection
from personal_affairs.storage.repositories.event_outbox import EventOutboxRepository
from personal_affairs.storage.repositories.webhooks import WebhookSubscriptionsRepository


def _worker_id() -> str:
    return f"{gethostname()}:{id(object())}"


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


async def _deliver(sub: dict, event: dict, cfg) -> tuple[bool, str, str]:
    body = _event_body(event)
    headers = {
        "Content-Type": "application/json",
        "X-PA-Event-Id": str(event["id"]),
        "X-PA-Event-Type": event["event_type"],
        "X-PA-Retry-Count": str(event["attempt_count"]),
        "X-PA-Signature": sign_payload(sub["secret"], body),
    }
    try:
        async with httpx.AsyncClient(timeout=cfg.webhook_timeout_seconds) as client:
            response = await client.post(sub["url"], content=body, headers=headers)
        if 200 <= response.status_code < 300:
            return True, "OK", ""
        return False, f"HTTP_{response.status_code}", (response.text or "")[:200]
    except Exception as exc:  # network/provider failures must not crash the loop
        return False, "NETWORK_ERROR", str(exc)[:200]


async def publish_once(worker_id: str) -> int:
    cfg = get_settings()
    with connection(cfg) as conn:
        repo = EventOutboxRepository(conn)
        repo.recover_expired_leases(cfg.webhook_lease_seconds)
        events = repo.claim_batch(worker_id, cfg.webhook_lease_seconds, cfg.webhook_batch_size)
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
            EventOutboxRepository(conn).mark_published(event["id"])
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
        else:
            attempt = int(event["attempt_count"])
            seed = int(UUID(str(event["id"])).int % 999999)
            retry_at = next_retry_at(attempt, datetime.now(UTC), seed)
            code = ",".join(sorted({f[0] for f in failures}))
            message = "; ".join(f[1] for f in failures[:2]) or code
            if retry_at is None:
                code = "DEAD:" + code
            repo.mark_failure(event["id"], attempt, retry_at, code, message)
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
