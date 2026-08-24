from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import CheckinPut, FocusCalibrationOut, HabitWeekOut
from personal_affairs.storage.repositories.habits import HabitsRepository
from personal_affairs.storage.repositories.preferences import PreferencesRepository

router = APIRouter(tags=["habits"])


def _user_timezone(conn: Connection, user_id: UUID) -> str:
    prefs = PreferencesRepository(conn).get(user_id, "Asia/Shanghai")
    return prefs["timezone"] if prefs else "Asia/Shanghai"


def _today(conn: Connection, user_id: UUID) -> date:
    tz = _user_timezone(conn, user_id)
    row = conn.execute("SELECT (now() AT TIME ZONE %s)::date AS today", (tz,)).fetchone()
    assert row is not None
    return row["today"]


@router.post("/items/{item_id}/checkin", dependencies=[Depends(require_csrf)], status_code=204)
def checkin(
    item_id: UUID,
    request: CheckinPut | None = None,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> None:
    day = request.checkin_date if request and request.checkin_date else _today(conn, user_id)
    if not HabitsRepository(conn).checkin(user_id, item_id, day):
        return not_found()


@router.delete("/items/{item_id}/checkin/{checkin_date}", status_code=204, dependencies=[Depends(require_csrf)])
def undo_checkin(
    item_id: UUID,
    checkin_date: date,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> None:
    HabitsRepository(conn).remove(user_id, item_id, checkin_date)


@router.get("/habits/week", response_model=list[HabitWeekOut])
def habits_week(
    week_offset: int = 0,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    today = _today(conn, user_id) - timedelta(weeks=max(0, min(week_offset, 8)))
    week_start = today - timedelta(days=today.weekday())
    return HabitsRepository(conn).week_matrix(user_id, week_start, today)


@router.get("/focus/week", response_model=FocusCalibrationOut)
def focus_week(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    today = _today(conn, user_id)
    week_start = today - timedelta(days=today.weekday())
    return HabitsRepository(conn).focus_calibration(user_id, week_start, today)
