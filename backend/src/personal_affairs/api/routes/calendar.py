from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import CalendarEventOut
from personal_affairs.application.calendar_query_service import CalendarQueryService
from personal_affairs.application.ics_service import build_feed, user_for_token
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.preferences import PreferencesRepository
from personal_affairs.storage.repositories.projects import ProjectsRepository

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events", response_model=list[CalendarEventOut])
def events(
    start: str = Query(alias="from"),
    end: str = Query(alias="to"),
    kinds: str | None = None,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    selected = set(kinds.split(",")) if kinds else None
    return CalendarQueryService(ItemsRepository(conn), ProjectsRepository(conn)).events(user_id, start, end, selected)


@router.get("/feed.ics")
def ics_feed(
    token: str = "",
    conn: Connection = Depends(db_conn),
) -> Response:
    """Public read-only feed. Token auth: calendar clients cannot carry sessions."""
    if not token:
        return not_found()
    user = user_for_token(conn, token)
    if not user:
        return not_found()
    feed = build_feed(conn, user["user_id"])
    return Response(content=feed, media_type="text/calendar; charset=utf-8")


@router.post("/feed-token", dependencies=[Depends(require_csrf)])
def regenerate_feed_token(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    token = PreferencesRepository(conn).regenerate_ics_token(user_id, "Asia/Shanghai")
    return {"ics_token": token}
