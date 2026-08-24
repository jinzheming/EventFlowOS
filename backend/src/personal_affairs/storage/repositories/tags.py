from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg import errors as pg_errors

from personal_affairs.domain.errors import ErrorCode, conflict_error, validation_error


class TagsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # ---------- tag CRUD ----------

    def list_tags(self, user_id: UUID) -> list[dict]:
        """All tags for the user with a non-archived item count per tag."""
        return list(
            self.conn.execute(
                """
                SELECT t.id, t.name, t.color, t.parent_id, t.pinned,
                       COUNT(DISTINCT it.item_id) FILTER (WHERE i.archived_at IS NULL AND i.deleted_at IS NULL) AS item_count
                FROM personal_affairs.tags t
                LEFT JOIN personal_affairs.item_tags it ON it.tag_id = t.id
                LEFT JOIN personal_affairs.items i ON i.id = it.item_id
                WHERE t.user_id = %s
                GROUP BY t.id
                ORDER BY t.created_at, t.name
                """,
                (user_id,),
            ).fetchall()
        )

    def get(self, user_id: UUID, tag_id: UUID) -> dict | None:
        return self.conn.execute(
            "SELECT id, name, color, parent_id, pinned FROM personal_affairs.tags WHERE user_id = %s AND id = %s",
            (user_id, tag_id),
        ).fetchone()

    def has_children(self, user_id: UUID, tag_id: UUID) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM personal_affairs.tags WHERE user_id = %s AND parent_id = %s LIMIT 1",
            (user_id, tag_id),
        ).fetchone()
        return row is not None

    def create(self, user_id: UUID, name: str, color: str, parent_id: UUID | None) -> dict:
        try:
            row = self.conn.execute(
                """
                INSERT INTO personal_affairs.tags(user_id, name, color, parent_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id, name, color, parent_id
                """,
                (user_id, name, color, parent_id),
            ).fetchone()
        except pg_errors.UniqueViolation:
            raise conflict_error(ErrorCode.TAG_NAME_CONFLICT, "同名标签已存在") from None
        assert row is not None
        return row

    def patch(self, user_id: UUID, tag_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {"name", "color", "parent_id", "pinned"}
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key in allowed:
                updates.append(f"{key} = %s")
                params.append(value)
        if not updates:
            return self.get(user_id, tag_id)
        updates.append("updated_at = now()")
        params.extend([user_id, tag_id])
        try:
            row = self.conn.execute(
                f"""
                UPDATE personal_affairs.tags
                SET {', '.join(updates)}
                WHERE user_id = %s AND id = %s
                RETURNING id, name, color, parent_id
                """,
                params,
            ).fetchone()
        except pg_errors.UniqueViolation:
            raise conflict_error(ErrorCode.TAG_NAME_CONFLICT, "同名标签已存在") from None
        return row

    def delete(self, user_id: UUID, tag_id: UUID) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM personal_affairs.tags WHERE user_id = %s AND id = %s",
            (user_id, tag_id),
        )
        return cursor.rowcount > 0

    # ---------- item <-> tag linkage ----------

    def tags_for_items(self, user_id: UUID, item_ids: list[UUID]) -> dict[str, list[dict]]:
        if not item_ids:
            return {}
        rows = self.conn.execute(
            """
            SELECT it.item_id, t.id, t.name, t.color, t.parent_id, t.pinned
            FROM personal_affairs.item_tags it
            JOIN personal_affairs.tags t ON t.id = it.tag_id AND t.user_id = %s
            WHERE it.item_id = ANY(%s::uuid[])
            ORDER BY t.name
            """,
            (user_id, item_ids),
        ).fetchall()
        by_item: dict[str, list[dict]] = {}
        for row in rows:
            by_item.setdefault(str(row["item_id"]), []).append(
                {"id": row["id"], "name": row["name"], "color": row["color"], "parent_id": row["parent_id"]}
            )
        return by_item

    def attach_tags(self, user_id: UUID, rows: list[dict]) -> list[dict]:
        if not rows:
            return rows
        by_item = self.tags_for_items(user_id, [row["id"] for row in rows])
        for row in rows:
            row["tags"] = by_item.get(str(row["id"]), [])
        return rows

    def replace_item_tags(self, user_id: UUID, item_id: UUID, tag_ids: list[UUID]) -> None:
        """Replace the full tag set of an item (idempotent; empty list clears)."""
        if tag_ids:
            owned = self.conn.execute(
                "SELECT id FROM personal_affairs.tags WHERE user_id = %s AND id = ANY(%s::uuid[])",
                (user_id, tag_ids),
            ).fetchall()
            owned_ids = {str(row["id"]) for row in owned}
            missing = [str(tag_id) for tag_id in tag_ids if str(tag_id) not in owned_ids]
            if missing:
                raise validation_error(
                    ErrorCode.TAG_ITEM_FORBIDDEN,
                    f"标签不存在或不属于当前用户：{', '.join(missing)}",
                )
        self.conn.execute("DELETE FROM personal_affairs.item_tags WHERE item_id = %s", (item_id,))
        for tag_id in tag_ids:
            self.conn.execute(
                "INSERT INTO personal_affairs.item_tags(item_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (item_id, tag_id),
            )

    def items_for_tag(
        self,
        user_id: UUID,
        tag_id: UUID,
        include_done: bool,
        scope: Any | None,
        recursive: bool,
        limit: int,
    ) -> list[dict]:
        """Items linked to the tag (and, when recursive, to its children)."""
        # 延迟导入避免 items_repo ↔ tags_repo 的模块级循环导入
        from personal_affairs.storage.repositories.items import ITEM_COLUMNS

        tag_ids = [tag_id]
        if recursive:
            children = self.conn.execute(
                "SELECT id FROM personal_affairs.tags WHERE user_id = %s AND parent_id = %s",
                (user_id, tag_id),
            ).fetchall()
            tag_ids.extend(row["id"] for row in children)
        where: list[str] = ["i.archived_at IS NULL", "i.deleted_at IS NULL", "it.tag_id = ANY(%s::uuid[])"]
        params: list[Any] = [user_id, tag_ids]
        if not include_done:
            where.append("i.status NOT IN ('done', 'cancelled')")
        if scope is not None:
            where.append("i.scope = %s")
            params.append(scope.value)
        params.append(limit)
        rows = list(
            self.conn.execute(
                f"""
                SELECT {ITEM_COLUMNS}
                FROM personal_affairs.item_tags it
                JOIN personal_affairs.items i ON i.id = it.item_id
                LEFT JOIN personal_affairs.projects p ON p.id = i.project_id AND p.user_id = i.user_id
                WHERE i.user_id = %s AND {' AND '.join(where)}
                ORDER BY i.due_date NULLS LAST, i.due_at NULLS LAST, i.priority DESC, i.updated_at DESC
                LIMIT %s
                """,
                params,
            ).fetchall()
        )
        seen: set[str] = set()
        unique: list[dict] = []
        for row in rows:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            unique.append(row)
        self.attach_tags(user_id, unique)
        from personal_affairs.storage.repositories.people import PeopleRepository

        return PeopleRepository(self.conn).attach_people(user_id, unique)
