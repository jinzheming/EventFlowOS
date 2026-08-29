from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from personal_affairs import __version__
from personal_affairs.api.middleware import RequestIdMiddleware
from personal_affairs.api.problem_details import domain_error_handler, unhandled_error_handler
from personal_affairs.api.routes import (
    agent_proposals,
    auth,
    calendar,
    export,
    focus,
    habits,
    integrations_feishu,
    items,
    people,
    preferences,
    project_groups,
    projects,
    push,
    reminders,
    saved_views,
    system,
    tags,
    webhooks,
)
from personal_affairs.config import Settings, get_settings
from personal_affairs.domain.errors import DomainError
from personal_affairs.storage.database import close_pool, connection
from personal_affairs.storage.migrations import run_migrations
from personal_affairs.storage.repositories.users import UsersRepository


def _csv_values(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _is_production(cfg: Settings) -> bool:
    return cfg.app_env.lower() == "production"


def _docs_enabled(cfg: Settings) -> bool:
    return cfg.api_docs_enabled if cfg.api_docs_enabled is not None else not _is_production(cfg)


def _allowed_hosts(cfg: Settings) -> list[str]:
    allowed_hosts = _csv_values(cfg.allowed_hosts)
    if _is_production(cfg) and not allowed_hosts:
        raise RuntimeError(
            "PERSONAL_AFFAIRS_ALLOWED_HOSTS must be set when PERSONAL_AFFAIRS_APP_ENV=production."
        )
    return allowed_hosts


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    cfg = get_settings()
    if cfg.app_env in {"development", "test"}:
        run_migrations(cfg.database_url)
    if cfg.bootstrap_username and cfg.bootstrap_password:
        with connection(cfg) as conn:
            UsersRepository(conn).ensure_bootstrap_user(
                cfg.bootstrap_username, cfg.bootstrap_password, cfg.default_timezone
            )
            conn.commit()
    yield
    close_pool()


def create_app() -> FastAPI:
    cfg = get_settings()
    docs_enabled = _docs_enabled(cfg)
    app = FastAPI(
        title="EventFlowOS API",
        version=__version__,
        openapi_url="/api/v1/openapi.json" if docs_enabled else None,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    allowed_hosts = _allowed_hosts(cfg)
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(system.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(agent_proposals.router, prefix="/api/v1")
    app.include_router(integrations_feishu.router, prefix="/api/v1")
    app.include_router(items.router, prefix="/api/v1")
    app.include_router(focus.router, prefix="/api/v1")
    app.include_router(habits.router, prefix="/api/v1")
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(project_groups.router, prefix="/api/v1")
    app.include_router(calendar.router, prefix="/api/v1")
    app.include_router(reminders.router, prefix="/api/v1")
    app.include_router(preferences.router, prefix="/api/v1")
    app.include_router(tags.router, prefix="/api/v1")
    app.include_router(saved_views.router, prefix="/api/v1")
    app.include_router(people.router, prefix="/api/v1")
    app.include_router(export.router, prefix="/api/v1")
    app.include_router(push.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")
    return app


app = create_app()


def main() -> None:
    uvicorn.run("personal_affairs.api.app:app", host="0.0.0.0", port=8080, reload=False)
