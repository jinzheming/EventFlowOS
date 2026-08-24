import re
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from personal_affairs.application.idempotency import json_safe
from personal_affairs.domain.enums import ItemScope, ItemStatus
from personal_affairs.storage.repositories.people import PeopleRepository
from personal_affairs.storage.repositories.tags import TagsRepository

ITEM_COLUMNS = """
    i.id, i.scope, i.project_id, p.name AS project_name, i.title, i.notes, i.status, i.priority,
    i.all_day, i.start_at, i.due_at, i.start_date, i.due_date, i.waiting_on, i.waiting_follow_up_date,
    i.recurrence_freq, i.recurrence_interval, i.recurrence_until, i.recurrence_count, i.estimated_minutes,
    i.completed_at, i.cancelled_at, i.archived_at, i.deleted_at, i.version, i.created_at, i.updated_at
"""

ITEM_RETURN_COLUMNS = """
    id, scope, project_id, NULL::text AS project_name, title, notes, status, priority,
    all_day, start_at, due_at, start_date, due_date, waiting_on, waiting_follow_up_date,
    recurrence_freq, recurrence_interval, recurrence_until, recurrence_count, estimated_minutes,
    completed_at, cancelled_at, archived_at, deleted_at, version, created_at, updated_at
"""


class ItemsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def replay_create_request(
        self, user_id: UUID, resource_type: str, client_request_id: str, request_hash: str
    ) -> tuple[str, dict | None]:
        row = self.conn.execute(
            """
            SELECT create_request_hash, response_snapshot
            FROM personal_affairs.create_requests
            WHERE user_id = %s AND resource_type = %s AND client_request_id = %s
            """,
            (user_id, resource_type, client_request_id),
        ).fetchone()
        if not row:
            return "missing", None
        if row["create_request_hash"] != request_hash:
            return "conflict", None
        return "replay", row["response_snapshot"]

    def record_create_request(
        self,
        user_id: UUID,
        client_request_id: str,
        request_hash: str,
        resource_type: str,
        resource_id: UUID,
        response_snapshot: dict,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO personal_affairs.create_requests(
                user_id, client_request_id, create_request_hash, resource_type, resource_id, response_snapshot
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, client_request_id, resource_type) DO NOTHING
            """,
            (user_id, client_request_id, request_hash, resource_type, resource_id, Jsonb(json_safe(response_snapshot))),
        )

    def list_items(
        self,
        user_id: UUID,
        scope: ItemScope | None,
        include_archived: bool = False,
        project_id: UUID | None = None,
        status: ItemStatus | None = None,
        limit: int = 100,
        search: str | None = None,
        deleted: bool = False,
    ) -> list[dict]:
        where: list[str] = ["i.user_id = %s"]
        params: list[Any] = [user_id]
        if scope:
            where.append("i.scope = %s")
            params.append(scope.value)
        if not include_archived:
            where.append("i.archived_at IS NULL")
        where.append("i.deleted_at IS NOT NULL" if deleted else "i.deleted_at IS NULL")
        if project_id:
            where.append("i.project_id = %s")
            params.append(project_id)
        if status:
            where.append("i.status = %s")
            params.append(status.value)
        if search and search.strip():
            term = re.sub(r"([%_\\])", r"\\\1", search.strip())
            where.append("(i.title ILIKE %s ESCAPE '\\' OR i.notes ILIKE %s ESCAPE '\\')")
            params.extend([f"%{term}%", f"%{term}%"])
        params.append(limit)
        rows = list(
            self.conn.execute(
                f"""
                SELECT {ITEM_COLUMNS}
                FROM personal_affairs.items i
                LEFT JOIN personal_affairs.projects p ON p.id = i.project_id AND p.user_id = i.user_id
                WHERE {' AND '.join(where)}
                ORDER BY i.archived_at NULLS FIRST, i.due_date NULLS LAST, i.due_at NULLS LAST,
                         i.priority DESC, i.updated_at DESC
                LIMIT %s
                """,
                params,
            ).fetchall()
        )
        TagsRepository(self.conn).attach_tags(user_id, rows)
        return PeopleRepository(self.conn).attach_people(user_id, rows)

    def get_item(self, user_id: UUID, item_id: UUID) -> dict | None:
        row = self.conn.execute(
            f"""
            SELECT {ITEM_COLUMNS}
            FROM personal_affairs.items i
            LEFT JOIN personal_affairs.projects p ON p.id = i.project_id AND p.user_id = i.user_id
            WHERE i.user_id = %s AND i.id = %s
            """,
            (user_id, item_id),
        ).fetchone()
        if row:
            TagsRepository(self.conn).attach_tags(user_id, [row])
            PeopleRepository(self.conn).attach_people(user_id, [row])
        return row

    def create_item(self, user_id: UUID, payload: dict[str, Any]) -> dict:
        row = self.conn.execute(
            f"""
            INSERT INTO personal_affairs.items(
                user_id, scope, project_id, title, notes, status, priority, all_day,
                start_at, due_at, start_date, due_date, waiting_on, waiting_follow_up_date,
                recurrence_freq, recurrence_interval, recurrence_until, recurrence_count, estimated_minutes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {ITEM_RETURN_COLUMNS}
            """,
            (
                user_id,
                payload["scope"],
                payload.get("project_id"),
                payload["title"],
                payload.get("notes"),
                payload.get("status", "inbox"),
                payload.get("priority", "normal"),
                payload.get("all_day", True),
                payload.get("start_at"),
                payload.get("due_at"),
                payload.get("start_date"),
                payload.get("due_date"),
                payload.get("waiting_on"),
                payload.get("waiting_follow_up_date"),
                payload.get("recurrence_freq"),
                payload.get("recurrence_interval", 1),
                payload.get("recurrence_until"),
                payload.get("recurrence_count"),
                payload.get("estimated_minutes"),
            ),
        ).fetchone()
        assert row is not None
        return self.get_item(user_id, row["id"]) or row

    def patch_item(self, user_id: UUID, item_id: UUID, expected_version: int, patch: dict[str, Any]) -> dict | None:
        allowed = {
            "title",
            "notes",
            "status",
            "scope",
            "priority",
            "project_id",
            "all_day",
            "start_at",
            "due_at",
            "start_date",
            "due_date",
            "waiting_on",
            "waiting_follow_up_date",
            "recurrence_freq",
            "recurrence_interval",
            "recurrence_until",
            "recurrence_count",
            "estimated_minutes",
        }
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key in allowed:
                updates.append(f"{key} = %s")
                params.append(value)
        if "status" in patch:
            if patch["status"] == "done":
                updates.append("completed_at = COALESCE(completed_at, now())")
            elif patch["status"] == "cancelled":
                updates.append("cancelled_at = COALESCE(cancelled_at, now())")
            else:
                updates.append("completed_at = NULL")
                updates.append("cancelled_at = NULL")
        if not updates:
            return self.get_item(user_id, item_id)
        updates.append("version = version + 1")
        updates.append("updated_at = now()")
        params.extend([user_id, item_id, expected_version])
        row = self.conn.execute(
            f"""
            UPDATE personal_affairs.items
            SET {', '.join(updates)}
            WHERE user_id = %s AND id = %s AND version = %s
            RETURNING id
            """,
            params,
        ).fetchone()
        if not row:
            return None
        return self.get_item(user_id, item_id)

    def set_archive(self, user_id: UUID, item_id: UUID, archived: bool) -> dict | None:
        row = self.conn.execute(
            """
            UPDATE personal_affairs.items
            SET archived_at = CASE WHEN %s THEN now() ELSE NULL END, version = version + 1, updated_at = now()
            WHERE user_id = %s AND id = %s
            RETURNING id
            """,
            (archived, user_id, item_id),
        ).fetchone()
        if not row:
            return None
        return self.get_item(user_id, item_id)

    def soft_delete(self, user_id: UUID, item_id: UUID) -> dict | None:
        row = self.conn.execute(
            """
            UPDATE personal_affairs.items
            SET deleted_at = now(), version = version + 1, updated_at = now()
            WHERE user_id = %s AND id = %s AND deleted_at IS NULL
            RETURNING id
            """,
            (user_id, item_id),
        ).fetchone()
        return row

    def restore_deleted(self, user_id: UUID, item_id: UUID) -> dict | None:
        row = self.conn.execute(
            """
            UPDATE personal_affairs.items
            SET deleted_at = NULL, version = version + 1, updated_at = now()
            WHERE user_id = %s AND id = %s AND deleted_at IS NOT NULL
            RETURNING id
            """,
            (user_id, item_id),
        ).fetchone()
        if not row:
            return None
        return self.get_item(user_id, item_id)

    def purge(self, user_id: UUID, item_id: UUID) -> bool:
        # 子表 item_tags/item_people/reminders/reminder_deliveries 均 ON DELETE CASCADE
        row = self.conn.execute(
            "DELETE FROM personal_affairs.items WHERE user_id = %s AND id = %s AND deleted_at IS NOT NULL RETURNING id",
            (user_id, item_id),
        ).fetchone()
        return row is not None

    def cancel_pending_deliveries(self, user_id: UUID, item_id: UUID) -> None:
        self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET status = 'cancelled', updated_at = now()
            WHERE user_id = %s AND item_id = %s AND status IN ('pending','retry_wait','delivering')
            """,
            (user_id, item_id),
        )

    def list_calendar_items(self, user_id: UUID, starts_before: str, ends_after: str) -> list[dict]:
        rows = list(
            self.conn.execute(
                f"""
                SELECT {ITEM_COLUMNS}
                FROM personal_affairs.items i
                LEFT JOIN personal_affairs.projects p ON p.id = i.project_id AND p.user_id = i.user_id
                WHERE i.user_id = %s
                  AND i.archived_at IS NULL
                  AND i.deleted_at IS NULL
                  AND i.status NOT IN ('cancelled', 'inbox')
                  AND (
                    (i.all_day = true AND COALESCE(i.due_date, i.start_date) IS NOT NULL
                     AND COALESCE(i.start_date, i.due_date) <= %s::date
                     AND COALESCE(i.due_date, i.start_date) >= %s::date)
                    OR
                    (i.all_day = false AND COALESCE(i.due_at, i.start_at) IS NOT NULL
                     AND COALESCE(i.start_at, i.due_at) <= %s::timestamptz
                     AND COALESCE(i.due_at, i.start_at) >= %s::timestamptz)
                  )
                ORDER BY COALESCE(i.start_at, i.due_at) NULLS LAST, COALESCE(i.start_date, i.due_date) NULLS LAST
                """,
                (user_id, starts_before, ends_after, starts_before, ends_after),
            ).fetchall()
        )
        TagsRepository(self.conn).attach_tags(user_id, rows)
        return PeopleRepository(self.conn).attach_people(user_id, rows)
