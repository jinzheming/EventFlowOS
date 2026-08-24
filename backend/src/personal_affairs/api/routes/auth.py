from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from psycopg import Connection

from personal_affairs.api.dependencies import (
    current_session,
    current_user_id,
    db_conn,
    require_csrf,
    settings,
)
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import (
    LoginRequest,
    SessionOut,
    TokenCreate,
    TokenCreated,
    TokenOut,
)
from personal_affairs.config import Settings
from personal_affairs.domain.errors import DomainError, ErrorCode
from personal_affairs.storage.repositories.tokens import TokensRepository
from personal_affairs.storage.repositories.users import UsersRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SessionOut)
def login(
    request: LoginRequest,
    response: Response,
    conn: Connection = Depends(db_conn),
    cfg: Settings = Depends(settings),
) -> SessionOut:
    users = UsersRepository(conn)
    user = users.verify_password(request.username, request.password)
    if not user:
        raise DomainError(ErrorCode.BAD_CREDENTIALS, "Username or password is invalid.", 401)
    session = users.create_session(user["id"])
    response.set_cookie(
        cfg.session_cookie_name,
        session["token"],
        httponly=True,
        secure=cfg.app_env == "production",
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )
    return SessionOut(
        user_id=user["id"],
        username=user["username"],
        csrf_token=session["csrf_token"],
        timezone=user["timezone"],
    )


@router.get("/session", response_model=SessionOut)
def session(session_data: dict = Depends(current_session)) -> SessionOut:
    return SessionOut(
        user_id=session_data["user_id"],
        username=session_data["username"],
        csrf_token=session_data.get("csrf_token") or "",
        timezone=session_data["timezone"],
    )


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(
    request: Request,
    response: Response,
    _: dict = Depends(current_session),
    conn: Connection = Depends(db_conn),
    cfg: Settings = Depends(settings),
) -> None:
    token = request.cookies.get(cfg.session_cookie_name)
    if token:
        UsersRepository(conn).delete_session(token)
    response.delete_cookie(cfg.session_cookie_name)


@router.post("/tokens", response_model=TokenCreated, dependencies=[Depends(require_csrf)])
def create_token(
    request: TokenCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> TokenCreated:
    expires_at = (
        datetime.now(UTC) + timedelta(days=request.expires_in_days)
        if request.expires_in_days is not None
        else None
    )
    return TokensRepository(conn).create(user_id, request.name, request.scopes, expires_at)


@router.get("/tokens", response_model=list[TokenOut])
def list_tokens(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return TokensRepository(conn).list_for_user(user_id)


@router.delete("/tokens/{token_id}", status_code=204, dependencies=[Depends(require_csrf)])
def revoke_token(
    token_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not TokensRepository(conn).revoke(user_id, token_id):
        return not_found()
    return Response(status_code=204)
