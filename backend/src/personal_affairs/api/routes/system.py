from fastapi import APIRouter

from personal_affairs.config import get_settings
from personal_affairs.storage.database import connection

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict:
    cfg = get_settings()
    with connection(cfg) as conn:
        row = conn.execute(
            "SELECT version FROM personal_affairs.schema_migrations ORDER BY applied_at DESC LIMIT 1"
        ).fetchone()
    return {"status": "ready", "schema_version": row["version"] if row else None}
