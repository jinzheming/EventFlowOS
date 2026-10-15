from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from personal_affairs.application.idempotency import json_safe


class WriteTargetsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list_for_user(self, user_id: UUID, active_only: bool = False) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, name, target_type, target_url, format_key, field_mapping, instructions,
                   active, created_at, updated_at
            FROM personal_affairs.write_targets
            WHERE user_id = %s
              AND (%s = false OR active = true)
            ORDER BY active DESC, created_at DESC
            """,
            (user_id, active_only),
        ).fetchall()
        return list(rows)

    def create(
        self,
        user_id: UUID,
        name: str,
        target_type: str,
        target_url: str,
        format_key: str,
        field_mapping: dict[str, Any],
        instructions: str | None,
        active: bool,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.write_targets(
                user_id, name, target_type, target_url, format_key, field_mapping, instructions, active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, name, target_type, target_url, format_key, field_mapping, instructions,
                      active, created_at, updated_at
            """,
            (
                user_id,
                name,
                target_type,
                target_url,
                format_key,
                Jsonb(json_safe(field_mapping)),
                instructions,
                active,
            ),
        ).fetchone()
        assert row is not None
        return row

    def patch(self, user_id: UUID, target_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {"name", "target_type", "target_url", "format_key", "field_mapping", "instructions", "active"}
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key not in allowed:
                continue
            updates.append(f"{key} = %s")
            params.append(Jsonb(json_safe(value)) if key == "field_mapping" else value)
        if not updates:
            return self.get(user_id, target_id)
        updates.append("updated_at = now()")
        params.extend([target_id, user_id])
        return self.conn.execute(
            f"""
            UPDATE personal_affairs.write_targets
            SET {', '.join(updates)}
            WHERE id = %s AND user_id = %s
            RETURNING id, name, target_type, target_url, format_key, field_mapping, instructions,
                      active, created_at, updated_at
            """,
            params,
        ).fetchone()

    def get(self, user_id: UUID, target_id: UUID) -> dict | None:
        return self.conn.execute(
            """
            SELECT id, name, target_type, target_url, format_key, field_mapping, instructions,
                   active, created_at, updated_at
            FROM personal_affairs.write_targets
            WHERE id = %s AND user_id = %s
            """,
            (target_id, user_id),
        ).fetchone()

    def delete(self, user_id: UUID, target_id: UUID) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.write_targets WHERE id = %s AND user_id = %s RETURNING id",
            (target_id, user_id),
        ).fetchone()
        return row is not None
