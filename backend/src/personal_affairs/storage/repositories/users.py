from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from psycopg import Connection

ph = PasswordHasher()


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


class UsersRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def ensure_bootstrap_user(self, username: str, password: str, timezone: str) -> None:
        exists = self.conn.execute(
            "SELECT id FROM personal_affairs.users WHERE username = %s",
            (username,),
        ).fetchone()
        if exists:
            return
        self.conn.execute(
            """
            INSERT INTO personal_affairs.users(username, password_hash, timezone)
            VALUES (%s, %s, %s)
            """,
            (username, ph.hash(password), timezone),
        )

    def verify_password(self, username: str, password: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT id, username::text AS username, password_hash, timezone
            FROM personal_affairs.users
            WHERE username = %s
            """,
            (username,),
        ).fetchone()
        if not row:
            return None
        try:
            ph.verify(row["password_hash"], password)
        except VerifyMismatchError:
            return None
        if ph.check_needs_rehash(row["password_hash"]):
            self.conn.execute(
                "UPDATE personal_affairs.users SET password_hash = %s, updated_at = now() WHERE id = %s",
                (ph.hash(password), row["id"]),
            )
        return {"id": row["id"], "username": row["username"], "timezone": row["timezone"]}

    def create_session(self, user_id: UUID, ttl_days: int = 30) -> dict:
        token = token_urlsafe(48)
        csrf = token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(days=ttl_days)
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.sessions(user_id, token_hash, csrf_token, expires_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id, csrf_token, expires_at
            """,
            (user_id, hash_token(token), csrf, expires_at),
        ).fetchone()
        assert row is not None
        return {"token": token, "csrf_token": row["csrf_token"], "expires_at": row["expires_at"]}

    def get_session(self, token: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT s.id AS session_id, s.csrf_token, u.id AS user_id, u.username::text AS username, u.timezone
            FROM personal_affairs.sessions s
            JOIN personal_affairs.users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.expires_at > now()
            """,
            (hash_token(token),),
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE personal_affairs.sessions SET last_seen_at = now() WHERE id = %s",
                (row["session_id"],),
            )
        return row

    def delete_session(self, token: str) -> None:
        self.conn.execute(
            "DELETE FROM personal_affairs.sessions WHERE token_hash = %s",
            (hash_token(token),),
        )

    def change_password(self, user_id: UUID, current_password: str, new_password: str) -> bool:
        row = self.conn.execute(
            "SELECT username::text AS username, password_hash FROM personal_affairs.users WHERE id = %s",
            (user_id,),
        ).fetchone()
        if not row:
            return False
        try:
            ph.verify(row["password_hash"], current_password)
        except VerifyMismatchError:
            return False
        self.conn.execute(
            "UPDATE personal_affairs.users SET password_hash = %s, updated_at = now() WHERE id = %s",
            (ph.hash(new_password), user_id),
        )
        return True
