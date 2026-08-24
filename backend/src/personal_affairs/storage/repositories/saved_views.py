from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from personal_affairs.domain.errors import ErrorCode, conflict_error

COLUMNS = "id, name, spec, sort_order, created_at, updated_at"


class SavedViewsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list(self, user_id: UUID) -> list[dict]:
        return list(
            self.conn.execute(
                f"""
                SELECT {COLUMNS}
                FROM personal_affairs.saved_views
                WHERE user_id = %s
                ORDER BY sort_order, lower(name)
                """,
                (user_id,),
            ).fetchall()
        )

    def create(self, user_id: UUID, name: str, spec: dict[str, Any], sort_order: int) -> dict:
        try:
            row = self.conn.execute(
                f"""
                INSERT INTO personal_affairs.saved_views(user_id, name, spec, sort_order)
                VALUES (%s, %s, %s, %s)
                RETURNING {COLUMNS}
                """,
                (user_id, name.strip(), Jsonb(spec), sort_order),
            ).fetchone()
        except pg_errors.UniqueViolation:
            raise conflict_error(ErrorCode.VIEW_NAME_CONFLICT, "同名视图已存在") from None
        assert row is not None
        return row

    def update(self, user_id: UUID, view_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {"name", "spec", "sort_order"}
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key in allowed:
                updates.append(f"{key} = %s")
                params.append(value.strip() if key == "name" else Jsonb(value) if key == "spec" else value)
        if not updates:
            return self.conn.execute(
                f"SELECT {COLUMNS} FROM personal_affairs.saved_views WHERE user_id = %s AND id = %s",
                (user_id, view_id),
            ).fetchone()
        updates.append("updated_at = now()")
        params.extend([user_id, view_id])
        try:
            return self.conn.execute(
                f"""
                UPDATE personal_affairs.saved_views
                SET {', '.join(updates)}
                WHERE user_id = %s AND id = %s
                RETURNING {COLUMNS}
                """,
                params,
            ).fetchone()
        except pg_errors.UniqueViolation:
            raise conflict_error(ErrorCode.VIEW_NAME_CONFLICT, "同名视图已存在") from None

    def delete(self, user_id: UUID, view_id: UUID) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.saved_views WHERE user_id = %s AND id = %s RETURNING id",
            (user_id, view_id),
        ).fetchone()
        return row is not None
