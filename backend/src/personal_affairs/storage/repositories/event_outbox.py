from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from personal_affairs.application.idempotency import json_safe


class EventOutboxRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def record(
        self,
        user_id: UUID,
        event_type: str,
        aggregate: str,
        aggregate_id: UUID,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO personal_affairs.event_outbox(user_id, event_type, aggregate, aggregate_id, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, event_type, aggregate, aggregate_id, Jsonb(json_safe(payload or {}))),
        )

    def claim_batch(self, worker_id: str, lease_seconds: int, limit: int) -> list[dict]:
        rows = self.conn.execute(
            """
            WITH due AS (
                SELECT id
                FROM personal_affairs.event_outbox
                WHERE published_at IS NULL
                  AND (claimed_at IS NULL OR claimed_at < now() - make_interval(secs => %s))
                  AND (retry_at IS NULL OR retry_at <= now())
                ORDER BY created_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE personal_affairs.event_outbox e
            SET claimed_at = now(), claimed_by = %s, attempt_count = e.attempt_count + 1
            FROM due
            WHERE e.id = due.id
            RETURNING e.id, e.user_id, e.event_type, e.aggregate, e.aggregate_id, e.payload, e.attempt_count
            """,
            (lease_seconds, limit, worker_id),
        ).fetchall()
        return list(rows)

    def recover_expired_leases(self, lease_seconds: int) -> int:
        cursor = self.conn.execute(
            """
            UPDATE personal_affairs.event_outbox
            SET claimed_at = NULL, claimed_by = NULL
            WHERE published_at IS NULL
              AND claimed_at IS NOT NULL
              AND claimed_at < now() - make_interval(secs => %s)
            """,
            (lease_seconds,),
        )
        return cursor.rowcount

    def mark_published(self, event_id: UUID) -> None:
        self.conn.execute(
            "UPDATE personal_affairs.event_outbox SET published_at = now() WHERE id = %s",
            (event_id,),
        )

    def mark_failure(
        self,
        event_id: UUID,
        attempt_count: int,
        retry_at: datetime | None,
        code: str,
        message: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE personal_affairs.event_outbox
            SET claimed_at = NULL, claimed_by = NULL, retry_at = %s,
                last_error_code = %s, last_error_message = %s
            WHERE id = %s
            """,
            (retry_at, code, message[:500], event_id),
        )

    def list_events(
        self,
        user_id: UUID,
        limit: int = 100,
        event_type: str | None = None,
    ) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, event_type, aggregate, aggregate_id, payload, created_at,
                   attempt_count, published_at, claimed_at, last_error_code, last_error_message
            FROM personal_affairs.event_outbox
            WHERE user_id = %s
              AND (%s::text IS NULL OR event_type = %s)
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, event_type, event_type, limit),
        ).fetchall()
        return list(rows)
