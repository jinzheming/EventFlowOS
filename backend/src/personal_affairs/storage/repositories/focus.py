from uuid import UUID

from psycopg import Connection

SESSION_SELECT = """
    SELECT f.id, f.item_id, i.title AS item_title, f.started_at, f.ended_at, f.duration_seconds, f.created_at
    FROM personal_affairs.focus_sessions f
    JOIN personal_affairs.items i ON i.id = f.item_id
"""


class FocusRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def active(self, user_id: UUID) -> dict | None:
        return self.conn.execute(
            f"""
            {SESSION_SELECT}
            WHERE f.user_id = %s AND f.ended_at IS NULL
            """,
            (user_id,),
        ).fetchone()

    def start(self, user_id: UUID, item_id: UUID) -> dict | None:
        existing = self.active(user_id)
        if existing:
            return existing
        owns_item = self.conn.execute(
            "SELECT 1 FROM personal_affairs.items WHERE id = %s AND user_id = %s",
            (item_id, user_id),
        ).fetchone()
        if not owns_item:
            return None
        self.conn.execute(
            """
            INSERT INTO personal_affairs.focus_sessions(user_id, item_id)
            VALUES (%s, %s)
            """,
            (user_id, item_id),
        )
        return self.active(user_id)

    def stop(self, user_id: UUID, item_id: UUID) -> dict | None:
        row = self.conn.execute(
            """
            UPDATE personal_affairs.focus_sessions
            SET ended_at = now(),
                duration_seconds = GREATEST(1, EXTRACT(EPOCH FROM (now() - started_at))::int)
            WHERE user_id = %s AND item_id = %s AND ended_at IS NULL
            RETURNING id
            """,
            (user_id, item_id),
        ).fetchone()
        if not row:
            return None
        return self.conn.execute(
            f"{SESSION_SELECT} WHERE f.id = %s",
            (row["id"],),
        ).fetchone()

    def summary_for_item(self, user_id: UUID, item_id: UUID) -> dict:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(duration_seconds), 0) AS total_seconds, COUNT(id) AS session_count
            FROM personal_affairs.focus_sessions
            WHERE user_id = %s AND item_id = %s AND ended_at IS NOT NULL
            """,
            (user_id, item_id),
        ).fetchone()
        return dict(row)

    def today(self, user_id: UUID, timezone: str) -> dict:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(duration_seconds), 0) AS total_seconds, COUNT(id) AS session_count
            FROM personal_affairs.focus_sessions
            WHERE user_id = %s AND ended_at IS NOT NULL
              AND (started_at AT TIME ZONE %s)::date = (now() AT TIME ZONE %s)::date
            """,
            (user_id, timezone, timezone),
        ).fetchone()
        return dict(row)
