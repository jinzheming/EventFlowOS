import asyncio
import contextlib
import json
from datetime import UTC, datetime
from socket import gethostname
from uuid import UUID
from zoneinfo import ZoneInfo

from personal_affairs.application.digest_service import build_evening, build_morning
from personal_affairs.config import Settings, get_settings
from personal_affairs.domain.enums import DeliveryChannel, DeliveryStatus
from personal_affairs.domain.reminder_state import classify_notification_error, next_retry_at
from personal_affairs.notifications.adapters import NotificationAdapter
from personal_affairs.storage.database import connection
from personal_affairs.storage.repositories.event_outbox import EventOutboxRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.push import PushRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository


def _worker_id() -> str:
    return f"{gethostname()}:{id(object())}"


async def deliver_once(worker_id: str) -> int:
    cfg = get_settings()
    adapter = NotificationAdapter(cfg)
    with connection(cfg) as conn:
        repo = RemindersRepository(conn)
        repo.recover_expired_leases()
        deliveries = repo.claim_due(worker_id, cfg.reminder_lease_seconds, cfg.reminder_batch_size)
        for delivery in deliveries:
            EventOutboxRepository(conn).record(
                delivery["user_id"],
                "reminder.fired",
                "delivery",
                delivery["id"],
                {"reminder_id": delivery["reminder_id"], "item_id": delivery["item_id"], "channel": delivery["channel"]},
            )
        conn.commit()
    for delivery in deliveries:
        await _deliver_delivery(worker_id, delivery, adapter)
    return len(deliveries)


async def _deliver_delivery(worker_id: str, delivery: dict, adapter: NotificationAdapter) -> None:
    cfg = get_settings()
    with connection(cfg) as conn:
        item = ItemsRepository(conn).get_item(delivery["user_id"], delivery["item_id"])
    title = "事项提醒"
    body = item["title"] if item else f"Reminder {delivery['reminder_id']}"
    try:
        result = await adapter.send(DeliveryChannel(delivery["channel"]), title, body)
        classification = classify_notification_error(result)
        if classification.status == DeliveryStatus.DELIVERED:
            with connection(cfg) as conn:
                RemindersRepository(conn).mark_delivered(
                    worker_id, delivery["id"], result.provider_message_id
                )
                conn.commit()
            if delivery["channel"] == DeliveryChannel.IN_APP.value:
                await _send_web_push(cfg, delivery["user_id"], title, body)
            return
        error_message = result.body or classification.code
    except Exception as exc:  # provider failures must not crash the worker loop
        classification = classify_notification_error(exc)
        error_message = str(exc)

    attempt_count = int(delivery["attempt_count"])
    jitter_seed = int(UUID(str(delivery["id"])).int % 999999)
    retry_at = next_retry_at(attempt_count, datetime.now(UTC), jitter_seed)
    status = DeliveryStatus.RETRY_WAIT if classification.retryable and retry_at else DeliveryStatus.DEAD
    with connection(cfg) as conn:
        RemindersRepository(conn).mark_failure(
            worker_id,
            delivery["id"],
            status,
            classification.code,
            error_message,
            retry_at,
        )
        if status == DeliveryStatus.DEAD:
            EventOutboxRepository(conn).record(
                delivery["user_id"],
                "delivery.failed",
                "delivery",
                delivery["id"],
                {"reminder_id": delivery["reminder_id"], "item_id": delivery["item_id"],
                 "channel": delivery["channel"], "code": classification.code},
            )
        conn.commit()


async def _send_web_push(cfg: Settings, user_id: UUID, title: str, body: str) -> None:
    """Best-effort Web Push fan-out on in-app delivery. Failures never affect delivery state."""
    if not (cfg.vapid_public_key and cfg.vapid_private_key):
        return
    try:
        from pywebpush import (  # pyright: ignore[reportMissingImports] pywebpush 无 py.typed
            WebPushException,
            webpush,
        )
    except ImportError:
        return
    try:
        with connection(cfg) as conn:
            subscriptions = PushRepository(conn).list_for_user(user_id)
        stale: list[UUID] = []
        for subscription in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription["endpoint"],
                        "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
                    },
                    data=json.dumps({"title": title, "body": body}),
                    vapid_private_key=cfg.vapid_private_key,
                    vapid_claims={"sub": cfg.vapid_subject},
                    timeout=cfg.notification_provider_timeout_seconds,
                )
            except WebPushException as exc:
                if exc.response is not None and exc.response.status_code in (404, 410):
                    stale.append(subscription["id"])
            except Exception:
                continue
        if stale:
            with connection(cfg) as conn:
                repo = PushRepository(conn)
                for subscription_id in stale:
                    repo.delete_by_id(subscription_id)
                conn.commit()
    except Exception:
        return  # push 是尽力而为的旁路，任何失败都不影响主投递链路


async def dispatch_digests() -> None:
    """Send morning/evening digests (Web Push) once per user per kind per local day."""
    cfg = get_settings()
    due: list[tuple[UUID, str, str]] = []
    with connection(cfg) as conn:
        rows = list(
            conn.execute(
                """
                SELECT u.id, p.timezone, p.digest_morning_enabled, p.digest_evening_enabled,
                       p.digest_morning_time, p.digest_evening_time
                FROM personal_affairs.users u
                JOIN personal_affairs.user_preferences p ON p.user_id = u.id
                """
            ).fetchall()
        )
        for row in rows:
            tz = row["timezone"] or "Asia/Shanghai"
            now_local = datetime.now(ZoneInfo(tz))
            today = now_local.date()
            hm = now_local.strftime("%H:%M")
            for kind, enabled, conf in (
                ("morning", row["digest_morning_enabled"], row["digest_morning_time"]),
                ("evening", row["digest_evening_enabled"], row["digest_evening_time"]),
            ):
                if not enabled or hm < conf:
                    continue
                already = conn.execute(
                    "SELECT 1 FROM personal_affairs.digest_log WHERE user_id = %s AND kind = %s AND sent_on = %s",
                    (row["id"], kind, today),
                ).fetchone()
                if already:
                    continue
                content = build_morning(conn, row["id"], today, tz) if kind == "morning" else build_evening(conn, row["id"], today, tz)
                if not content:
                    continue
                title, body = content
                conn.execute(
                    """
                    INSERT INTO personal_affairs.digest_log(user_id, kind, sent_on, title, body)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (row["id"], kind, today, title, body),
                )
                due.append((row["id"], title, body))
        conn.commit()
    for user_id, title, body in due:
        await _send_web_push(cfg, user_id, title, body)


async def run_forever() -> None:
    cfg = get_settings()
    worker_id = _worker_id()
    while True:
        await deliver_once(worker_id)
        # digest failures must never crash the reminder loop
        with contextlib.suppress(Exception):
            await dispatch_digests()
        await asyncio.sleep(cfg.reminder_poll_seconds)


def main() -> None:
    asyncio.run(run_forever())
