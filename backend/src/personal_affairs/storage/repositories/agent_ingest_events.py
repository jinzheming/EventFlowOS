from typing import Any
from uuid import UUID

from psycopg import Connection


class AgentIngestEventsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def record_received(self, user_id: UUID, payload: dict[str, Any]) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.agent_ingest_events(
                user_id, source_type, tenant_key, conversation_key, event_id,
                message_id, sender_key, payload_digest, text_preview
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_type, tenant_key, conversation_key, (COALESCE(event_id, '')), (COALESCE(message_id, '')))
            DO UPDATE SET updated_at = personal_affairs.agent_ingest_events.updated_at
            RETURNING id, source_type, tenant_key, conversation_key, event_id, message_id,
                      sender_key, payload_digest, text_preview, status, proposal_id,
                      applied_item_id, error_code, created_at, updated_at
            """,
            (
                user_id,
                payload["source_type"],
                payload["tenant_key"],
                payload["conversation_key"],
                payload.get("event_id"),
                payload.get("message_id"),
                payload.get("sender_key"),
                payload["payload_digest"],
                payload.get("text_preview"),
            ),
        ).fetchone()
        assert row is not None
        return row

    def mark_status(
        self,
        user_id: UUID,
        event_id: UUID,
        status: str,
        proposal_id: UUID | None = None,
        applied_item_id: UUID | None = None,
        error_code: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE personal_affairs.agent_ingest_events
            SET status = %s, proposal_id = %s, applied_item_id = %s, error_code = %s, updated_at = now()
            WHERE user_id = %s AND id = %s
            """,
            (status, proposal_id, applied_item_id, error_code, user_id, event_id),
        )
