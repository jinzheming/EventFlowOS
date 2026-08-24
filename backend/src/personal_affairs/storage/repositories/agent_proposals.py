from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from personal_affairs.application.idempotency import json_safe

PROPOSAL_COLUMNS = """
    id, source_type, source_ref, risk_tier, confidence, state, proposed_action,
    proposed_payload, evidence, reason, target_item_id, applied_item_id,
    expires_at, decided_at, decided_by_actor, decision_note, created_at, updated_at
"""


class AgentProposalsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def create(self, user_id: UUID, payload: dict[str, Any]) -> dict:
        row = self.conn.execute(
            f"""
            INSERT INTO personal_affairs.agent_proposals(
                user_id, source_type, source_ref, risk_tier, confidence, proposed_action,
                proposed_payload, evidence, reason, target_item_id, expires_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {PROPOSAL_COLUMNS}
            """,
            (
                user_id,
                payload["source_type"],
                payload.get("source_ref"),
                payload.get("risk_tier", "l2"),
                payload.get("confidence"),
                payload.get("proposed_action", "create_item"),
                Jsonb(json_safe(payload["proposed_payload"])),
                Jsonb(json_safe(payload.get("evidence") or {})),
                payload.get("reason"),
                payload.get("target_item_id"),
                payload.get("expires_at"),
            ),
        ).fetchone()
        assert row is not None
        return row

    def list_pending(self, user_id: UUID, state: str | None, limit: int) -> list[dict]:
        where = ["user_id = %s"]
        params: list[Any] = [user_id]
        if state:
            where.append("state = %s")
            params.append(state)
        params.append(limit)
        return list(
            self.conn.execute(
                f"""
                SELECT {PROPOSAL_COLUMNS}
                FROM personal_affairs.agent_proposals
                WHERE {' AND '.join(where)}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            ).fetchall()
        )

    def get(self, user_id: UUID, proposal_id: UUID) -> dict | None:
        return self.conn.execute(
            f"""
            SELECT {PROPOSAL_COLUMNS}
            FROM personal_affairs.agent_proposals
            WHERE user_id = %s AND id = %s
            """,
            (user_id, proposal_id),
        ).fetchone()

    def get_for_update(self, user_id: UUID, proposal_id: UUID) -> dict | None:
        return self.conn.execute(
            f"""
            SELECT {PROPOSAL_COLUMNS}
            FROM personal_affairs.agent_proposals
            WHERE user_id = %s AND id = %s
            FOR UPDATE
            """,
            (user_id, proposal_id),
        ).fetchone()

    def mark_decided(
        self,
        user_id: UUID,
        proposal_id: UUID,
        state: str,
        decided_by_actor: str,
        decision_note: str | None = None,
        applied_item_id: UUID | None = None,
        proposed_payload: dict[str, Any] | None = None,
    ) -> dict | None:
        updates = [
            "state = %s",
            "decided_by_actor = %s",
            "decision_note = %s",
            "decided_at = now()",
            "updated_at = now()",
        ]
        params: list[Any] = [state, decided_by_actor, decision_note]
        if applied_item_id is not None:
            updates.append("applied_item_id = %s")
            params.append(applied_item_id)
        if proposed_payload is not None:
            updates.append("proposed_payload = %s")
            params.append(Jsonb(json_safe(proposed_payload)))
        params.extend([user_id, proposal_id])
        return self.conn.execute(
            f"""
            UPDATE personal_affairs.agent_proposals
            SET {', '.join(updates)}
            WHERE user_id = %s AND id = %s
            RETURNING {PROPOSAL_COLUMNS}
            """,
            params,
        ).fetchone()
