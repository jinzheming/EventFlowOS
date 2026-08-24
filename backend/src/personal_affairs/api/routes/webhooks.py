from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import WebhookCreate, WebhookCreated, WebhookEventOut, WebhookOut
from personal_affairs.storage.repositories.event_outbox import EventOutboxRepository
from personal_affairs.storage.repositories.webhooks import (
    WebhookSubscriptionsRepository,
    generate_webhook_secret,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _event_status(row: dict) -> str:
    if row["published_at"] is not None:
        return "published"
    if row["last_error_code"] and row["last_error_code"].startswith("DEAD"):
        return "dead"
    if row["claimed_at"] is not None:
        return "delivering"
    if row["last_error_code"] is not None:
        return "retrying"
    return "pending"


@router.get("", response_model=list[WebhookOut])
def list_webhooks(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return WebhookSubscriptionsRepository(conn).list_for_user(user_id)


@router.post("", response_model=WebhookCreated, dependencies=[Depends(require_csrf)])
def create_webhook(
    request: WebhookCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    secret = generate_webhook_secret()
    return WebhookSubscriptionsRepository(conn).create(user_id, request.name, request.url, request.events, secret)


@router.delete("/{webhook_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_webhook(
    webhook_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not WebhookSubscriptionsRepository(conn).delete(user_id, webhook_id):
        return not_found()
    return Response(status_code=204)


@router.get("/events", response_model=list[WebhookEventOut])
def list_events(
    limit: int = Query(100, ge=1, le=500),
    event_type: str | None = None,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    rows = EventOutboxRepository(conn).list_events(user_id, limit, event_type)
    for row in rows:
        row["status"] = _event_status(row)
    return rows
