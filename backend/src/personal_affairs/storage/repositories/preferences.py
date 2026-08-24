from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from personal_affairs.application.idempotency import json_safe


class PreferencesRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def get(self, user_id: UUID, default_timezone: str) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.user_preferences(user_id, timezone)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
            RETURNING timezone, work_filters, personal_filters, calendar_filters, weekly_review_enabled, desktop_notifications, identity_scope_rules,
                   digest_morning_enabled, digest_evening_enabled, digest_morning_time, digest_evening_time, ics_token
            """,
            (user_id, default_timezone),
        ).fetchone()
        if row:
            return row
        return self.conn.execute(
            """
            SELECT timezone, work_filters, personal_filters, calendar_filters, weekly_review_enabled, desktop_notifications, identity_scope_rules,
                   digest_morning_enabled, digest_evening_enabled, digest_morning_time, digest_evening_time, ics_token
            FROM personal_affairs.user_preferences
            WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()

    def patch(self, user_id: UUID, patch: dict[str, Any], default_timezone: str) -> dict:
        self.get(user_id, default_timezone)
        allowed = {"timezone", "work_filters", "personal_filters", "calendar_filters", "weekly_review_enabled", "desktop_notifications", "identity_scope_rules", "digest_morning_enabled", "digest_evening_enabled", "digest_morning_time", "digest_evening_time"}
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key in allowed:
                updates.append(f"{key} = %s")
                params.append(Jsonb(json_safe(value)) if key.endswith("_filters") or key == "identity_scope_rules" else value)
        if not updates:
            return self.get(user_id, default_timezone)
        updates.append("updated_at = now()")
        params.append(user_id)
        return self.conn.execute(
            f"""
            UPDATE personal_affairs.user_preferences
            SET {', '.join(updates)}
            WHERE user_id = %s
            RETURNING timezone, work_filters, personal_filters, calendar_filters, weekly_review_enabled, desktop_notifications, identity_scope_rules,
                   digest_morning_enabled, digest_evening_enabled, digest_morning_time, digest_evening_time, ics_token
            """,
            params,
        ).fetchone()

    def regenerate_ics_token(self, user_id: UUID, default_timezone: str) -> str:
        import secrets

        self.get(user_id, default_timezone)
        token = secrets.token_urlsafe(24)
        self.conn.execute(
            "UPDATE personal_affairs.user_preferences SET ics_token = %s, updated_at = now() WHERE user_id = %s",
            (token, user_id),
        )
        return token
