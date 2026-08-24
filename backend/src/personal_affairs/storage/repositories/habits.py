from datetime import date, timedelta
from typing import Any
from uuid import UUID

from psycopg import Connection


class HabitsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def checkin(self, user_id: UUID, item_id: UUID, checkin_date: date) -> bool:
        owns = self.conn.execute(
            "SELECT 1 FROM personal_affairs.items WHERE id = %s AND user_id = %s",
            (item_id, user_id),
        ).fetchone()
        if not owns:
            return False
        self.conn.execute(
            """
            INSERT INTO personal_affairs.habit_checkins(item_id, user_id, checkin_date)
            VALUES (%s, %s, %s)
            ON CONFLICT (item_id, checkin_date) DO NOTHING
            """,
            (item_id, user_id, checkin_date),
        )
        return True

    def remove(self, user_id: UUID, item_id: UUID, checkin_date: date) -> None:
        self.conn.execute(
            "DELETE FROM personal_affairs.habit_checkins WHERE user_id = %s AND item_id = %s AND checkin_date = %s",
            (user_id, item_id, checkin_date),
        )

    def week_matrix(self, user_id: UUID, week_start: date, today: date) -> list[dict[str, Any]]:
        """Recurring (habit) items with their check-in dates in [week_start, today]."""
        items = list(
            self.conn.execute(
                """
                SELECT i.id, i.title, i.scope, i.recurrence_freq
                FROM personal_affairs.items i
                WHERE i.user_id = %s AND i.archived_at IS NULL AND i.deleted_at IS NULL
                  AND i.status NOT IN ('done', 'cancelled', 'inbox')
                  AND i.recurrence_freq IN ('daily', 'weekly')
                ORDER BY i.scope, i.title
                """,
                (user_id,),
            ).fetchall()
        )
        if not items:
            return []
        checkins = list(
            self.conn.execute(
                """
                SELECT item_id, checkin_date
                FROM personal_affairs.habit_checkins
                WHERE user_id = %s AND item_id = ANY(%s::uuid[])
                  AND checkin_date >= %s AND checkin_date <= %s
                """,
                (user_id, [item["id"] for item in items], week_start - timedelta(days=60), today),
            ).fetchall()
        )
        by_item: dict[Any, set[date]] = {}
        for row in checkins:
            by_item.setdefault(row["item_id"], set()).add(row["checkin_date"])

        result = []
        for item in items:
            dates = by_item.get(item["id"], set())
            week_days = [week_start + timedelta(days=offset) for offset in range(7)]
            week_flags = [day in dates for day in week_days]
            streak = 0
            cursor = today if today in dates else today - timedelta(days=1)
            while cursor in dates:
                streak += 1
                cursor -= timedelta(days=1)
            elapsed_days = min((today - week_start).days + 1, 7)
            result.append(
                {
                    "item_id": item["id"],
                    "title": item["title"],
                    "scope": item["scope"],
                    "recurrence_freq": item["recurrence_freq"],
                    "week": week_flags,
                    "week_done": sum(week_flags),
                    "week_target": elapsed_days if item["recurrence_freq"] == "daily" else 1,
                    "streak": streak,
                    "today_done": today in dates,
                }
            )
        return result

    def focus_calibration(self, user_id: UUID, week_start: date, week_end: date) -> dict[str, Any]:
        """Per-session comparison: each completed session's actual seconds vs the
        item's estimated minutes (sessions on items without an estimate are
        excluded from the estimated side)."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS session_count,
                   COALESCE(SUM(f.duration_seconds), 0) AS actual_seconds,
                   COUNT(*) FILTER (WHERE i.estimated_minutes IS NOT NULL) AS calibrated_count,
                   COALESCE(SUM(i.estimated_minutes) FILTER (WHERE i.estimated_minutes IS NOT NULL), 0) * 60 AS estimated_seconds,
                   COALESCE(SUM(f.duration_seconds) FILTER (WHERE i.estimated_minutes IS NOT NULL), 0) AS calibrated_actual_seconds
            FROM personal_affairs.focus_sessions f
            JOIN personal_affairs.items i ON i.id = f.item_id
            WHERE f.user_id = %s AND f.ended_at IS NOT NULL
              AND f.started_at::date >= %s AND f.started_at::date <= %s
            """,
            (user_id, week_start, week_end),
        ).fetchone()
        return dict(row)
