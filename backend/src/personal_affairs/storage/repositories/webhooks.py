from secrets import token_urlsafe
from uuid import UUID

from psycopg import Connection


def generate_webhook_secret() -> str:
    return token_urlsafe(24)


class WebhookSubscriptionsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list_for_user(self, user_id: UUID) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, name, url, events, active, created_at, updated_at
            FROM personal_affairs.webhook_subscriptions
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return list(rows)

    def create(self, user_id: UUID, name: str, url: str, events: list[str], secret: str) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.webhook_subscriptions(user_id, name, url, secret, events)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, name, url, events, active, created_at, updated_at
            """,
            (user_id, name, url, secret, events),
        ).fetchone()
        assert row is not None
        return dict(row) | {"secret": secret}

    def delete(self, user_id: UUID, webhook_id: UUID) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.webhook_subscriptions WHERE id = %s AND user_id = %s RETURNING id",
            (webhook_id, user_id),
        ).fetchone()
        return row is not None

    def list_active_for_event(self, user_id: UUID, event_type: str) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, url, secret
            FROM personal_affairs.webhook_subscriptions
            WHERE user_id = %s AND active = true AND %s = ANY(events)
            """,
            (user_id, event_type),
        ).fetchall()
        return list(rows)
