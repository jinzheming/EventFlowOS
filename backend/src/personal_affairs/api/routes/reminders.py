from uuid import UUID

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf, settings
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import ChannelsOut, DeliveryOut, ReminderHealthOut, SnoozePut
from personal_affairs.config import Settings
from personal_affairs.storage.repositories.event_outbox import EventOutboxRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("/channels", response_model=ChannelsOut)
def channels(cfg: Settings = Depends(settings)) -> dict:
    """仅暴露配置布尔值，绝不回传 webhook/topic URL。"""
    return {
        "feishu_configured": bool(cfg.feishu_webhook_url),
        "ntfy_configured": bool(cfg.ntfy_topic_url),
    }


@router.get("/deliveries", response_model=list[DeliveryOut])
def deliveries(
    limit: int = Query(100, ge=1, le=500),
    channel: str | None = Query(None, pattern="^(in_app|feishu|ntfy)$"),
    status: str | None = Query(None, pattern="^(pending|delivering|delivered|retry_wait|dead|cancelled)$"),
    unseen: bool = Query(False),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return RemindersRepository(conn).list_deliveries(user_id, limit, channel, status, unseen)


@router.post("/deliveries/{delivery_id}/ack", response_model=DeliveryOut, dependencies=[Depends(require_csrf)])
def ack_delivery(
    delivery_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    row = RemindersRepository(conn).acknowledge(user_id, delivery_id)
    if not row:
        return not_found()
    EventOutboxRepository(conn).record(user_id, "reminder.acked", "delivery", delivery_id, {"item_id": row["item_id"]})
    return row


@router.post("/deliveries/{delivery_id}/snooze", response_model=DeliveryOut, dependencies=[Depends(require_csrf)])
def snooze_delivery(
    delivery_id: UUID,
    request: SnoozePut,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    row = RemindersRepository(conn).snooze(user_id, delivery_id, request.snooze_until)
    if not row:
        return not_found()
    EventOutboxRepository(conn).record(
        user_id, "reminder.snoozed", "delivery", delivery_id,
        {"item_id": row["item_id"], "snooze_until": request.snooze_until.isoformat()},
    )
    return row


@router.post("/deliveries/{delivery_id}/retry", response_model=DeliveryOut, dependencies=[Depends(require_csrf)])
def retry_delivery(
    delivery_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    row = RemindersRepository(conn).retry_dead(user_id, delivery_id)
    if not row:
        return not_found()
    return row


@router.get("/health", response_model=ReminderHealthOut)
def health(conn: Connection = Depends(db_conn)) -> dict:
    return RemindersRepository(conn).health()
