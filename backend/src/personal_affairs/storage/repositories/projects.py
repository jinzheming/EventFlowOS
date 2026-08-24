from typing import Any
from uuid import UUID

from psycopg import Connection

PROJECT_COLUMNS = """
    id, name, goal, status, health, progress_mode, progress_percent, risk_summary, next_step,
    next_review_at, due_date, color, group_id, archived_at, version, created_at, updated_at
"""

LIST_COLUMNS = """
    p.id, p.name, p.goal, p.status, p.health, p.progress_mode, p.progress_percent, p.risk_summary, p.next_step,
    p.next_review_at, p.due_date, p.color, p.group_id, g.name AS group_name,
    p.archived_at, p.version, p.created_at, p.updated_at
"""


class ProjectsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list_projects(self, user_id: UUID, include_archived: bool = False, limit: int = 100) -> list[dict]:
        archived_sql = "" if include_archived else "AND archived_at IS NULL"
        return list(
            self.conn.execute(
                f"""
                SELECT {LIST_COLUMNS}
                FROM personal_affairs.projects p
                LEFT JOIN personal_affairs.project_groups g ON g.id = p.group_id
                WHERE p.user_id = %s {archived_sql}
                ORDER BY p.archived_at NULLS FIRST, p.updated_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            ).fetchall()
        )

    def get_project(self, user_id: UUID, project_id: UUID) -> dict | None:
        return self.conn.execute(
            f"SELECT {PROJECT_COLUMNS} FROM personal_affairs.projects WHERE user_id = %s AND id = %s",
            (user_id, project_id),
        ).fetchone()

    def create_project(self, user_id: UUID, payload: dict[str, Any]) -> dict:
        return self.conn.execute(
            f"""
            INSERT INTO personal_affairs.projects(
                user_id, name, goal, status, health, progress_mode, progress_percent,
                risk_summary, next_step, next_review_at, due_date, color, group_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {PROJECT_COLUMNS}
            """,
            (
                user_id,
                payload["name"],
                payload.get("goal"),
                payload.get("status", "planned"),
                payload.get("health", "unknown"),
                payload.get("progress_mode", "manual"),
                payload.get("progress_percent"),
                payload.get("risk_summary"),
                payload.get("next_step"),
                payload.get("next_review_at"),
                payload.get("due_date"),
                payload.get("color", "#2563EB"),
                payload.get("group_id"),
            ),
        ).fetchone()

    def patch_project(
        self, user_id: UUID, project_id: UUID, expected_version: int, patch: dict[str, Any]
    ) -> dict | None:
        allowed = {
            "name",
            "goal",
            "status",
            "health",
            "progress_mode",
            "progress_percent",
            "risk_summary",
            "next_step",
            "next_review_at",
            "due_date",
            "color",
            "group_id",
        }
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key in allowed:
                updates.append(f"{key} = %s")
                params.append(value)
        if not updates:
            return self.get_project(user_id, project_id)
        updates.append("version = version + 1")
        updates.append("updated_at = now()")
        params.extend([user_id, project_id, expected_version])
        row = self.conn.execute(
            f"""
            UPDATE personal_affairs.projects
            SET {', '.join(updates)}
            WHERE user_id = %s AND id = %s AND version = %s
            RETURNING {PROJECT_COLUMNS}
            """,
            params,
        ).fetchone()
        return row

    def set_archive(self, user_id: UUID, project_id: UUID, archived: bool) -> dict | None:
        row = self.conn.execute(
            f"""
            UPDATE personal_affairs.projects
            SET archived_at = CASE WHEN %s THEN now() ELSE NULL END, version = version + 1, updated_at = now()
            WHERE user_id = %s AND id = %s
            RETURNING {PROJECT_COLUMNS}
            """,
            (archived, user_id, project_id),
        ).fetchone()
        return row

    def create_milestone(self, user_id: UUID, project_id: UUID, payload: dict[str, Any]) -> dict:
        return self.conn.execute(
            """
            INSERT INTO personal_affairs.milestones(user_id, project_id, title, status, due_date, weight, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, project_id, title, status, due_date, weight, sort_order, created_at, updated_at
            """,
            (
                user_id,
                project_id,
                payload["title"],
                payload.get("status", "pending"),
                payload.get("due_date"),
                payload.get("weight", 1),
                payload.get("sort_order", 0),
            ),
        ).fetchone()

    def list_milestones(self, user_id: UUID, project_id: UUID) -> list[dict]:
        return list(
            self.conn.execute(
                """
                SELECT id, project_id, title, status, due_date, weight, sort_order, created_at, updated_at
                FROM personal_affairs.milestones
                WHERE user_id = %s AND project_id = %s
                ORDER BY sort_order, due_date NULLS LAST, created_at
                """,
                (user_id, project_id),
            ).fetchall()
        )

    def update_milestone(self, user_id: UUID, milestone_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {"title", "status", "due_date", "weight", "sort_order"}
        sets = [f"{key} = %s" for key in patch if key in allowed]
        if not sets:
            return self.conn.execute(
                """
                SELECT id, project_id, title, status, due_date, weight, sort_order, created_at, updated_at
                FROM personal_affairs.milestones WHERE user_id = %s AND id = %s
                """,
                (user_id, milestone_id),
            ).fetchone()
        params = [patch[key] for key in patch if key in allowed]
        params.extend([user_id, milestone_id])
        return self.conn.execute(
            f"""
            UPDATE personal_affairs.milestones
            SET {', '.join(sets)}, updated_at = now()
            WHERE user_id = %s AND id = %s
            RETURNING id, project_id, title, status, due_date, weight, sort_order, created_at, updated_at
            """,
            params,
        ).fetchone()

    def delete_milestone(self, user_id: UUID, milestone_id: UUID) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.milestones WHERE user_id = %s AND id = %s RETURNING id",
            (user_id, milestone_id),
        ).fetchone()
        return row is not None

    def list_calendar_milestones(self, user_id: UUID, starts_before: str, ends_after: str) -> list[dict]:
        return list(
            self.conn.execute(
                """
                SELECT m.id, m.project_id, p.name AS project_name, m.title, m.status, m.due_date, p.color
                FROM personal_affairs.milestones m
                JOIN personal_affairs.projects p ON p.id = m.project_id AND p.user_id = m.user_id
                WHERE m.user_id = %s AND p.archived_at IS NULL AND m.status <> 'cancelled'
                  AND m.due_date IS NOT NULL AND m.due_date <= %s::date AND m.due_date >= %s::date
                ORDER BY m.due_date, m.sort_order
                """,
                (user_id, starts_before, ends_after),
            ).fetchall()
        )

    def create_update(self, user_id: UUID, project_id: UUID, payload: dict[str, Any]) -> dict:
        return self.conn.execute(
            """
            INSERT INTO personal_affairs.project_updates(
                user_id, project_id, body, health, progress_percent, risk_summary, next_step, corrects_update_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, project_id, body, health, progress_percent, risk_summary, next_step, corrects_update_id, created_at
            """,
            (
                user_id,
                project_id,
                payload["body"],
                payload.get("health"),
                payload.get("progress_percent"),
                payload.get("risk_summary"),
                payload.get("next_step"),
                payload.get("corrects_update_id"),
            ),
        ).fetchone()

    def list_updates(self, user_id: UUID, project_id: UUID, limit: int = 50) -> list[dict]:
        return list(
            self.conn.execute(
                """
                SELECT id, project_id, body, health, progress_percent, risk_summary, next_step, corrects_update_id, created_at
                FROM personal_affairs.project_updates
                WHERE user_id = %s AND project_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, project_id, limit),
            ).fetchall()
        )
