from collections.abc import Iterator
from uuid import UUID

from fastapi import Depends, Header, Request
from psycopg import Connection

from personal_affairs.config import Settings, get_settings
from personal_affairs.domain.errors import DomainError, ErrorCode
from personal_affairs.storage.database import get_pool
from personal_affairs.storage.repositories.tokens import TokensRepository
from personal_affairs.storage.repositories.users import UsersRepository


def settings() -> Settings:
    return get_settings()


def db_conn() -> Iterator[Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def current_session(
    request: Request,
    conn: Connection = Depends(db_conn),
    cfg: Settings = Depends(settings),
) -> dict:
    """Resolve the caller to a user via cookie session or Bearer PAT.

    Returns a session-shaped dict carrying ``auth_method`` ("cookie" | "pat")
    plus ``pat_scopes`` for PAT callers. Routes only read user_id / csrf_token,
    so the extra keys are additive.
    """
    token = request.cookies.get(cfg.session_cookie_name)
    if token:
        session = UsersRepository(conn).get_session(token)
        if session:
            return dict(session) | {"auth_method": "cookie"}
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        pat = authorization[7:].strip()
        if pat:
            row = TokensRepository(conn).get_by_token(pat)
            if row:
                return {
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "csrf_token": None,
                    "auth_method": "pat",
                    "pat_scopes": list(row["scopes"] or []),
                }
    raise DomainError(ErrorCode.AUTH_REQUIRED, "Authentication is required.", 401)


def current_user_id(session: dict = Depends(current_session)) -> UUID:
    return session["user_id"]


def require_csrf(
    x_csrf_token: str | None = Header(default=None),
    session: dict = Depends(current_session),
) -> None:
    """Write gate: cookie sessions must present a matching CSRF header; PAT
    callers must carry the write scope (CSRF does not apply to them)."""
    if session.get("auth_method") == "pat":
        scopes: list[str] = list(session.get("pat_scopes") or [])
        if "write" not in scopes:
            raise DomainError(
                ErrorCode.PAT_SCOPE_FORBIDDEN,
                "This personal access token lacks the write scope.",
                403,
            )
        return
    if not x_csrf_token or x_csrf_token != session["csrf_token"]:
        raise DomainError(ErrorCode.CSRF_REQUIRED, "Valid CSRF token is required.", 403)


def if_match_version(if_match: str | None = Header(default=None)) -> int:
    if not if_match:
        raise DomainError(ErrorCode.VERSION_CONFLICT, "If-Match header is required.", 412)
    cleaned = if_match.strip().strip('"')
    if cleaned.startswith("v"):
        cleaned = cleaned[1:]
    try:
        return int(cleaned)
    except ValueError as exc:
        raise DomainError(ErrorCode.VERSION_CONFLICT, "If-Match header must be a version tag.", 412) from exc
