from uuid import UUID

from fastapi import APIRouter, Depends, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import FocusSessionOut, FocusSummaryOut
from personal_affairs.storage.repositories.focus import FocusRepository
from personal_affairs.storage.repositories.preferences import PreferencesRepository

router = APIRouter(tags=["focus"])


@router.post("/items/{item_id}/focus/start", response_model=FocusSessionOut, dependencies=[Depends(require_csrf)])
def start_focus(
    item_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    session = FocusRepository(conn).start(user_id, item_id)
    if not session:
        return not_found()
    return session


@router.post("/items/{item_id}/focus/stop", response_model=FocusSessionOut, dependencies=[Depends(require_csrf)])
def stop_focus(
    item_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    session = FocusRepository(conn).stop(user_id, item_id)
    if not session:
        return not_found()
    return session


@router.get("/focus/active", response_model=FocusSessionOut | None)
def active_focus(
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict | None:
    session = FocusRepository(conn).active(user_id)
    if not session:
        response.status_code = 204
        return None
    return session


@router.get("/focus/today", response_model=FocusSummaryOut)
def focus_today(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    prefs = PreferencesRepository(conn).get(user_id, "Asia/Shanghai")
    return FocusRepository(conn).today(user_id, prefs["timezone"] if prefs else "Asia/Shanghai")


@router.get("/items/{item_id}/focus/summary", response_model=FocusSummaryOut)
def focus_summary(
    item_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return FocusRepository(conn).summary_for_item(user_id, item_id)
