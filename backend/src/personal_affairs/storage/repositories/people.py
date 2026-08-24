from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg import errors as pg_errors

from personal_affairs.domain.errors import ErrorCode, conflict_error, validation_error


class PeopleRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list_people(self, user_id: UUID, include_inactive: bool = False) -> list[dict]:
        where = ["p.user_id = %s"]
        params: list[Any] = [user_id]
        if not include_inactive:
            where.append("p.active = true")
        return list(
            self.conn.execute(
                f"""
                SELECT p.id, p.name, p.identity, p.note, p.active,
                       COUNT(ip.item_id) AS item_count,
                       p.created_at, p.updated_at
                FROM personal_affairs.people p
                LEFT JOIN personal_affairs.item_people ip ON ip.person_id = p.id
                WHERE {' AND '.join(where)}
                GROUP BY p.id
                ORDER BY p.active DESC, COALESCE(NULLIF(btrim(p.identity), ''), '未设置'), p.name
                """,
                params,
            ).fetchall()
        )

    def get(self, user_id: UUID, person_id: UUID) -> dict | None:
        return self.conn.execute(
            """
            SELECT p.id, p.name, p.identity, p.note, p.active,
                   COUNT(ip.item_id) AS item_count,
                   p.created_at, p.updated_at
            FROM personal_affairs.people p
            LEFT JOIN personal_affairs.item_people ip ON ip.person_id = p.id
            WHERE p.user_id = %s AND p.id = %s
            GROUP BY p.id
            """,
            (user_id, person_id),
        ).fetchone()

    def find_by_name_identity(self, user_id: UUID, name: str, identity: str | None) -> dict | None:
        return self.conn.execute(
            """
            SELECT id, name, identity, note, active, created_at, updated_at
            FROM personal_affairs.people
            WHERE user_id = %s
              AND lower(btrim(name)) = lower(btrim(%s))
              AND COALESCE(lower(btrim(identity)), '') = COALESCE(lower(btrim(%s)), '')
            """,
            (user_id, name, identity),
        ).fetchone()

    def create(self, user_id: UUID, name: str, identity: str | None, note: str | None) -> dict:
        try:
            row = self.conn.execute(
                """
                INSERT INTO personal_affairs.people(user_id, name, identity, note)
                VALUES (%s, %s, %s, %s)
                RETURNING id, name, identity, note, active, 0 AS item_count, created_at, updated_at
                """,
                (user_id, name, identity, note),
            ).fetchone()
        except pg_errors.UniqueViolation:
            raise conflict_error(ErrorCode.PERSON_NAME_CONFLICT, "同名且同身份的人员已存在") from None
        assert row is not None
        return row

    def get_or_create(self, user_id: UUID, name: str, identity: str | None) -> dict:
        existing = self.find_by_name_identity(user_id, name, identity)
        if existing:
            return existing
        return self.create(user_id, name, identity, None)

    def patch(self, user_id: UUID, person_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {"name", "identity", "note", "active"}
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key in allowed:
                updates.append(f"{key} = %s")
                params.append(value)
        if not updates:
            return self.get(user_id, person_id)
        updates.append("updated_at = now()")
        params.extend([user_id, person_id])
        try:
            row = self.conn.execute(
                f"""
                UPDATE personal_affairs.people
                SET {', '.join(updates)}
                WHERE user_id = %s AND id = %s
                RETURNING id
                """,
                params,
            ).fetchone()
        except pg_errors.UniqueViolation:
            raise conflict_error(ErrorCode.PERSON_NAME_CONFLICT, "同名且同身份的人员已存在") from None
        if not row:
            return None
        return self.get(user_id, person_id)

    def delete(self, user_id: UUID, person_id: UUID) -> bool:
        try:
            cursor = self.conn.execute(
                "DELETE FROM personal_affairs.people WHERE user_id = %s AND id = %s",
                (user_id, person_id),
            )
        except pg_errors.ForeignKeyViolation:
            raise conflict_error(ErrorCode.PERSON_IN_USE, "该人员已被事项引用，请改为停用") from None
        return cursor.rowcount > 0

    def people_for_items(self, user_id: UUID, item_ids: list[UUID]) -> dict[str, list[dict]]:
        if not item_ids:
            return {}
        rows = self.conn.execute(
            """
            SELECT ip.item_id, p.id, p.name, p.identity, p.active, ip.role
            FROM personal_affairs.item_people ip
            JOIN personal_affairs.people p ON p.id = ip.person_id AND p.user_id = %s
            WHERE ip.item_id = ANY(%s::uuid[])
            ORDER BY CASE ip.role WHEN 'waiting' THEN 0 ELSE 1 END, p.name
            """,
            (user_id, item_ids),
        ).fetchall()
        by_item: dict[str, list[dict]] = {}
        for row in rows:
            by_item.setdefault(str(row["item_id"]), []).append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "identity": row["identity"],
                    "active": row["active"],
                    "role": row["role"],
                }
            )
        return by_item

    def attach_people(self, user_id: UUID, rows: list[dict]) -> list[dict]:
        if not rows:
            return rows
        by_item = self.people_for_items(user_id, [row["id"] for row in rows])
        for row in rows:
            row["people"] = by_item.get(str(row["id"]), [])
        return rows

    def replace_item_people(self, user_id: UUID, item_id: UUID, people: list[dict[str, Any]]) -> None:
        if people:
            person_ids = [person["person_id"] for person in people]
            owned = self.conn.execute(
                "SELECT id FROM personal_affairs.people WHERE user_id = %s AND id = ANY(%s::uuid[])",
                (user_id, person_ids),
            ).fetchall()
            owned_ids = {str(row["id"]) for row in owned}
            missing = [str(person_id) for person_id in person_ids if str(person_id) not in owned_ids]
            if missing:
                raise validation_error(
                    ErrorCode.PERSON_ITEM_FORBIDDEN,
                    f"人员不存在或不属于当前用户：{', '.join(missing)}",
                )
        self.conn.execute("DELETE FROM personal_affairs.item_people WHERE item_id = %s", (item_id,))
        for person in people:
            self.conn.execute(
                """
                INSERT INTO personal_affairs.item_people(item_id, person_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (item_id, person_id) DO UPDATE
                SET role = EXCLUDED.role, updated_at = now()
                """,
                (item_id, person["person_id"], person["role"]),
            )
