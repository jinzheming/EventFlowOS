from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf, settings
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.rate_limit import enforce_rate_limit, rate_limit_key_part
from personal_affairs.api.schemas import WebhookCreate, WebhookCreated, WebhookEventOut, WebhookOut
from personal_affairs.application.webhook_urls import WebhookUrlError, validate_webhook_url
from personal_affairs.config import Settings
from personal_affairs.domain.errors import DomainError, ErrorCode
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
    cfg: Settings = Depends(settings),
) -> dict:
    enforce_rate_limit(
        cfg,
        "webhook_create",
        rate_limit_key_part(user_id),
        cfg.webhook_create_rate_limit_attempts,
    )
    try:
        url = validate_webhook_url(
            request.url,
            allow_private=cfg.webhook_allow_private_urls,
            allowed_hosts=cfg.webhook_allowed_hosts,
        )
    except WebhookUrlError as exc:
        raise DomainError(ErrorCode.INVALID_REQUEST, str(exc), 422) from exc
    secret = generate_webhook_secret()
    return WebhookSubscriptionsRepository(conn).create(user_id, request.name, url, request.events, secret)


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
