from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

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
from personal_affairs.config import get_settings
from personal_affairs.domain.errors import DomainError
from personal_affairs.storage.database import close_pool, connection
from personal_affairs.storage.migrations import run_migrations
from personal_affairs.storage.repositories.users import UsersRepository


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
    app = FastAPI(
        title="Personal Affairs API",
        version=__version__,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(system.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(agent_proposals.router, prefix="/api/v1")
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
