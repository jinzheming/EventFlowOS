from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg import errors as pg_errors

from personal_affairs.domain.errors import ErrorCode, conflict_error

GROUP_COLUMNS = """
    id, name, color, sort_order, archived_at, created_at, updated_at
"""

LIST_SELECT = """
    SELECT g.id, g.name, g.color, g.sort_order, g.archived_at, g.created_at, g.updated_at,
           COUNT(p.id) FILTER (WHERE p.archived_at IS NULL) AS project_count,
           COUNT(p.id) FILTER (WHERE p.archived_at IS NULL AND p.health IN ('blocked', 'at_risk')) AS risk_count
    FROM personal_affairs.project_groups g
    LEFT JOIN personal_affairs.projects p ON p.group_id = g.id AND p.user_id = g.user_id
"""


class ProjectGroupsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list_groups(self, user_id: UUID, include_archived: bool = False) -> list[dict]:
        archived_sql = "" if include_archived else "AND g.archived_at IS NULL"
        return list(
            self.conn.execute(
                f"""
                {LIST_SELECT}
                WHERE g.user_id = %s {archived_sql}
                GROUP BY g.id
                ORDER BY g.sort_order, lower(g.name)
                """,
                (user_id,),
            ).fetchall()
        )

    def get(self, user_id: UUID, group_id: UUID) -> dict | None:
        return self.conn.execute(
            f"""
            {LIST_SELECT}
            WHERE g.user_id = %s AND g.id = %s
            GROUP BY g.id
            """,
            (user_id, group_id),
        ).fetchone()

    def find_by_name(self, user_id: UUID, name: str) -> dict | None:
        return self.conn.execute(
            f"""
            SELECT {GROUP_COLUMNS}
            FROM personal_affairs.project_groups
            WHERE user_id = %s AND lower(btrim(name)) = lower(btrim(%s)) AND archived_at IS NULL
            """,
            (user_id, name),
        ).fetchone()

    def create(self, user_id: UUID, name: str, color: str, sort_order: int) -> dict:
        try:
            row = self.conn.execute(
                """
                INSERT INTO personal_affairs.project_groups(user_id, name, color, sort_order)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, name.strip(), color, sort_order),
            ).fetchone()
        except pg_errors.UniqueViolation:
            raise conflict_error(ErrorCode.GROUP_NAME_CONFLICT, "同名分组已存在") from None
        assert row is not None
        return self.get(user_id, row["id"])

    def update(self, user_id: UUID, group_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {"name", "color", "sort_order"}
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key in allowed:
                updates.append(f"{key} = %s")
                params.append(value.strip() if key == "name" else value)
        if not updates:
            return self.get(user_id, group_id)
        updates.append("updated_at = now()")
        params.extend([user_id, group_id])
        try:
            row = self.conn.execute(
                f"""
                UPDATE personal_affairs.project_groups
                SET {', '.join(updates)}
                WHERE user_id = %s AND id = %s
                RETURNING id
                """,
                params,
            ).fetchone()
        except pg_errors.UniqueViolation:
            raise conflict_error(ErrorCode.GROUP_NAME_CONFLICT, "同名分组已存在") from None
        if not row:
            return None
        return self.get(user_id, group_id)

    def set_archive(self, user_id: UUID, group_id: UUID, archived: bool) -> dict | None:
        row = self.conn.execute(
            """
            UPDATE personal_affairs.project_groups
            SET archived_at = CASE WHEN %s THEN now() ELSE NULL END, updated_at = now()
            WHERE user_id = %s AND id = %s
            RETURNING id
            """,
            (archived, user_id, group_id),
        ).fetchone()
        if not row:
            return None
        return self.get(user_id, group_id)
