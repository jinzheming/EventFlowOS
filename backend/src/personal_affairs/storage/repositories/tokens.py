from datetime import datetime
from secrets import token_urlsafe
from uuid import UUID

from psycopg import Connection

from personal_affairs.storage.repositories.users import hash_token

PAT_PREFIX = "pa_"


def generate_pat() -> str:
    """Generate a personal access token: pa_ + ~40 chars of url-safe entropy."""
    return f"{PAT_PREFIX}{token_urlsafe(30)}"


class TokensRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def create(
        self,
        user_id: UUID,
        name: str,
        scopes: list[str],
        expires_at: datetime | None,
    ) -> dict:
        token = generate_pat()
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.personal_access_tokens(
                user_id, name, token_hash, scopes, expires_at
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id, name, scopes, expires_at, created_at
            """,
            (user_id, name, hash_token(token), scopes, expires_at),
        ).fetchone()
        assert row is not None
        return dict(row) | {"token": token}

    def get_by_token(self, token: str) -> dict | None:
        """Resolve a live (non-revoked, non-expired) token to its user.

        Updates last_used_at on successful resolution.
        """
        row = self.conn.execute(
            """
            SELECT t.id AS token_id, t.user_id, t.scopes,
                   u.username::text AS username, u.timezone
            FROM personal_affairs.personal_access_tokens t
            JOIN personal_affairs.users u ON u.id = t.user_id
            WHERE t.token_hash = %s
              AND t.revoked_at IS NULL
              AND (t.expires_at IS NULL OR t.expires_at > now())
            """,
            (hash_token(token),),
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE personal_affairs.personal_access_tokens SET last_used_at = now() WHERE id = %s",
                (row["token_id"],),
            )
        return row

    def list_for_user(self, user_id: UUID) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, name, scopes, expires_at, last_used_at, revoked_at, created_at
            FROM personal_affairs.personal_access_tokens
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return list(rows)

    def revoke(self, user_id: UUID, token_id: UUID) -> bool:
        row = self.conn.execute(
            """
            UPDATE personal_affairs.personal_access_tokens
            SET revoked_at = now()
            WHERE id = %s AND user_id = %s AND revoked_at IS NULL
            RETURNING id
            """,
            (token_id, user_id),
        ).fetchone()
        return row is not None
