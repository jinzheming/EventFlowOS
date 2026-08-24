from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf, settings
from personal_affairs.api.schemas import PreferencesOut, PreferencesPatch
from personal_affairs.config import Settings
from personal_affairs.storage.repositories.preferences import PreferencesRepository

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesOut)
def get_preferences(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
    cfg: Settings = Depends(settings),
) -> dict:
    return PreferencesRepository(conn).get(user_id, cfg.default_timezone)


@router.patch("", response_model=PreferencesOut, dependencies=[Depends(require_csrf)])
def patch_preferences(
    request: PreferencesPatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
    cfg: Settings = Depends(settings),
) -> dict:
    return PreferencesRepository(conn).patch(user_id, request.model_dump(exclude_unset=True), cfg.default_timezone)
