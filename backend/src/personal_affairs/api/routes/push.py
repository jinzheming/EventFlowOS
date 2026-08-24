from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg import Connection
from pydantic import BaseModel, Field

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf, settings
from personal_affairs.api.problem_details import not_found
from personal_affairs.config import Settings
from personal_affairs.storage.repositories.push import PushRepository

router = APIRouter(prefix="/push", tags=["push"])


class VapidKeyOut(BaseModel):
    enabled: bool
    public_key: str | None


class PushSubscriptionPut(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=200)


class PushSubscriptionDelete(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)


@router.get("/vapid-key", response_model=VapidKeyOut)
def vapid_key(cfg: Settings = Depends(settings)) -> dict:
    """公钥可公开；私钥绝不出 API。"""
    return {
        "enabled": bool(cfg.vapid_public_key and cfg.vapid_private_key),
        "public_key": cfg.vapid_public_key,
    }


@router.post("/subscriptions", status_code=201, dependencies=[Depends(require_csrf)])
def subscribe(
    request: PushSubscriptionPut,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return PushRepository(conn).upsert_subscription(user_id, request.endpoint, request.p256dh, request.auth)


@router.delete("/subscriptions", status_code=204, dependencies=[Depends(require_csrf)])
def unsubscribe(
    request: PushSubscriptionDelete,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> None:
    if not PushRepository(conn).delete_subscription(user_id, request.endpoint):
        return not_found()
