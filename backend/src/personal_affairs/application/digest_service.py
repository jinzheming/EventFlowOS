"""Morning/evening digest content builders.

Pure SQL assembly over existing tables; returns None when there is nothing
worth sending (empty digests stay silent by design).
"""

from datetime import date
from uuid import UUID

from psycopg import Connection

from personal_affairs.storage.repositories.habits import HabitsRepository


def _today_timed(conn: Connection, user_id: UUID, day: date, tz: str) -> list[dict]:
    return list(
        conn.execute(
            """
            SELECT i.title, i.start_at, i.due_at
            FROM personal_affairs.items i
            WHERE i.user_id = %s AND i.archived_at IS NULL AND i.deleted_at IS NULL
              AND i.status NOT IN ('done', 'cancelled', 'inbox')
              AND i.all_day = false
              AND (COALESCE(i.start_at, i.due_at) AT TIME ZONE %s)::date = %s
            ORDER BY COALESCE(i.start_at, i.due_at)
            """,
            (user_id, tz, day),
        ).fetchall()
    )


def _overdue_count(conn: Connection, user_id: UUID, day: date) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM personal_affairs.items i
        WHERE i.user_id = %s AND i.archived_at IS NULL AND i.deleted_at IS NULL
          AND i.status NOT IN ('done', 'cancelled', 'inbox')
          AND COALESCE(i.due_at::date, i.due_date, i.start_at::date, i.start_date) < %s
        """,
        (user_id, day),
    ).fetchone()
    assert row is not None
    return int(row["n"])


def _waiting_due_count(conn: Connection, user_id: UUID, day: date) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM personal_affairs.items i
        WHERE i.user_id = %s AND i.archived_at IS NULL AND i.deleted_at IS NULL
          AND i.status = 'waiting'
          AND (i.waiting_follow_up_date IS NULL OR i.waiting_follow_up_date <= %s)
        """,
        (user_id, day),
    ).fetchone()
    assert row is not None
    return int(row["n"])


def _completed_today(conn: Connection, user_id: UUID, day: date) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM personal_affairs.items i
        WHERE i.user_id = %s AND i.status = 'done'
          AND COALESCE(i.completed_at::date, i.updated_at::date) = %s
        """,
        (user_id, day),
    ).fetchone()
    assert row is not None
    return int(row["n"])


def build_morning(conn: Connection, user_id: UUID, day: date, tz: str) -> tuple[str, str] | None:
    timed = _today_timed(conn, user_id, day, tz)
    overdue = _overdue_count(conn, user_id, day)
    waiting = _waiting_due_count(conn, user_id, day)
    week_start = day.fromordinal(day.toordinal() - day.weekday())
    habits = HabitsRepository(conn).week_matrix(user_id, week_start, day)
    pending_habits = [habit for habit in habits if habit["recurrence_freq"] == "daily" and not habit["today_done"]]

    if not timed and not overdue and not waiting and not pending_habits:
        return None
    parts: list[str] = []
    if timed:
        parts.append(f"今天 {len(timed)} 件事，最早 {timed[0]['title']}")
    if overdue:
        parts.append(f"逾期 {overdue} 件")
    if waiting:
        parts.append(f"等待跟进 {waiting} 条")
    if pending_habits:
        parts.append(f"今日习惯 {len(pending_habits)} 个")
    return ("早安 · 今日速览", " · ".join(parts))


def build_evening(conn: Connection, user_id: UUID, day: date, tz: str) -> tuple[str, str] | None:
    completed = _completed_today(conn, user_id, day)
    week_start = day.fromordinal(day.toordinal() - day.weekday())
    habits = HabitsRepository(conn).week_matrix(user_id, week_start, day)
    daily_habits = [habit for habit in habits if habit["recurrence_freq"] == "daily"]
    habits_done = sum(1 for habit in daily_habits if habit["today_done"])
    focus = HabitsRepository(conn).focus_calibration(user_id, day, day)
    focus_minutes = round(focus["actual_seconds"] / 60)

    tomorrow = date.fromordinal(day.toordinal() + 1)
    tomorrow_timed = _today_timed(conn, user_id, tomorrow, tz)

    if not completed and not daily_habits and not focus_minutes:
        return None
    parts = [f"今天完成 {completed} 件"]
    if focus_minutes:
        parts.append(f"专注 {focus_minutes} 分钟")
    if daily_habits:
        parts.append(f"习惯打卡 {habits_done}/{len(daily_habits)}")
    if tomorrow_timed:
        parts.append(f"明天最早：{tomorrow_timed[0]['title']}")
    return ("晚安 · 今日收束", " · ".join(parts))
