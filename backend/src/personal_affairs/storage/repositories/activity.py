from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from personal_affairs.application.idempotency import json_safe


class ActivityRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def record(self, user_id: UUID, entity_type: str, entity_id: UUID, action: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO personal_affairs.activity_events(user_id, entity_type, entity_id, action, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, entity_type, entity_id, action, Jsonb(json_safe(payload))),
        )
