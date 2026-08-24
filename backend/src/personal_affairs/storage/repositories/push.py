from uuid import UUID

from psycopg import Connection


class PushRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def upsert_subscription(self, user_id: UUID, endpoint: str, p256dh: str, auth: str) -> dict:
        return self.conn.execute(
            """
            INSERT INTO personal_affairs.push_subscriptions(user_id, endpoint, p256dh, auth)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, endpoint) DO UPDATE
            SET p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth, updated_at = now()
            RETURNING id, endpoint, created_at
            """,
            (user_id, endpoint, p256dh, auth),
        ).fetchone()

    def delete_subscription(self, user_id: UUID, endpoint: str) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.push_subscriptions WHERE user_id = %s AND endpoint = %s RETURNING id",
            (user_id, endpoint),
        ).fetchone()
        return row is not None

    def list_for_user(self, user_id: UUID) -> list[dict]:
        return list(
            self.conn.execute(
                "SELECT id, endpoint, p256dh, auth FROM personal_affairs.push_subscriptions WHERE user_id = %s",
                (user_id,),
            ).fetchall()
        )

    def delete_by_id(self, subscription_id: UUID) -> None:
        self.conn.execute(
            "DELETE FROM personal_affairs.push_subscriptions WHERE id = %s",
            (subscription_id,),
        )
