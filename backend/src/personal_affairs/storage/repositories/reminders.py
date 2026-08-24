from datetime import UTC, datetime, timedelta
from uuid import UUID

from psycopg import Connection

from personal_affairs.domain.enums import DeliveryChannel, DeliveryStatus


class RemindersRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def get_active_for_item(self, user_id: UUID, item_id: UUID) -> dict | None:
        return self.conn.execute(
            """
            SELECT id, item_id, timing, offset_minutes, timezone, external_enabled, active, created_at, updated_at
            FROM personal_affairs.reminders
            WHERE user_id = %s AND item_id = %s AND active = true
            """,
            (user_id, item_id),
        ).fetchone()

    def upsert_for_item(self, user_id: UUID, item_id: UUID, payload: dict) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.reminders(
                user_id, item_id, timing, offset_minutes, timezone, external_enabled, active
            ) VALUES (%s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (item_id) WHERE active = true DO UPDATE
            SET timing = EXCLUDED.timing,
                offset_minutes = EXCLUDED.offset_minutes,
                timezone = EXCLUDED.timezone,
                external_enabled = EXCLUDED.external_enabled,
                updated_at = now()
            RETURNING id, item_id, timing, offset_minutes, timezone, external_enabled, active, created_at, updated_at
            """,
            (
                user_id,
                item_id,
                payload.get("timing", "before_due"),
                payload.get("offset_minutes", 10),
                payload.get("timezone", "Asia/Shanghai"),
                payload.get("external_enabled", False),
            ),
        ).fetchone()
        return row

    def deactivate_for_item(self, user_id: UUID, item_id: UUID) -> None:
        self.conn.execute(
            """
            UPDATE personal_affairs.reminders
            SET active = false, updated_at = now()
            WHERE user_id = %s AND item_id = %s AND active = true
            """,
            (user_id, item_id),
        )
        self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET status = 'cancelled', updated_at = now()
            WHERE user_id = %s AND item_id = %s AND status IN ('pending','retry_wait','delivering')
            """,
            (user_id, item_id),
        )

    def replace_pending_deliveries(
        self,
        user_id: UUID,
        reminder_id: UUID,
        item_id: UUID,
        scheduled_for: datetime,
        channels: list[DeliveryChannel],
    ) -> None:
        self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET status = 'cancelled', updated_at = now()
            WHERE user_id = %s AND reminder_id = %s AND status IN ('pending','retry_wait','delivering')
            """,
            (user_id, reminder_id),
        )
        for channel in channels:
            self.conn.execute(
                """
                INSERT INTO personal_affairs.reminder_deliveries(
                    user_id, reminder_id, item_id, channel, scheduled_for, status, next_attempt_at
                ) VALUES (%s, %s, %s, %s, %s, 'pending', %s)
                ON CONFLICT (reminder_id, scheduled_for, channel) DO UPDATE
                SET status = 'pending', next_attempt_at = EXCLUDED.next_attempt_at, updated_at = now()
                """,
                (user_id, reminder_id, item_id, channel.value, scheduled_for, scheduled_for),
            )

    def list_deliveries(
        self,
        user_id: UUID,
        limit: int = 100,
        channel: str | None = None,
        status: str | None = None,
        unseen: bool = False,
    ) -> list[dict]:
        return list(
            self.conn.execute(
                """
                SELECT id, reminder_id, item_id, channel, scheduled_for, status, attempt_count,
                       last_error_code, last_error_message, delivered_at, acknowledged_at, snooze_until,
                       created_at, updated_at
                FROM personal_affairs.reminder_deliveries
                WHERE user_id = %s
                  AND (%s::text IS NULL OR channel = %s)
                  AND (%s::text IS NULL OR status = %s)
                  AND (NOT %s OR (status = 'delivered' AND acknowledged_at IS NULL
                                  AND (snooze_until IS NULL OR snooze_until <= now())))
                ORDER BY scheduled_for DESC
                LIMIT %s
                """,
                (user_id, channel, channel, status, status, unseen, limit),
            ).fetchall()
        )

    def acknowledge(self, user_id: UUID, delivery_id: UUID) -> dict | None:
        return self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET acknowledged_at = now(), snooze_until = NULL, updated_at = now()
            WHERE user_id = %s AND id = %s AND status = 'delivered'
            RETURNING id, reminder_id, item_id, channel, scheduled_for, status, attempt_count,
                      last_error_code, last_error_message, delivered_at, acknowledged_at, snooze_until,
                      created_at, updated_at
            """,
            (user_id, delivery_id),
        ).fetchone()

    def snooze(self, user_id: UUID, delivery_id: UUID, snooze_until: datetime) -> dict | None:
        return self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET snooze_until = %s, acknowledged_at = NULL, updated_at = now()
            WHERE user_id = %s AND id = %s AND status = 'delivered'
            RETURNING id, reminder_id, item_id, channel, scheduled_for, status, attempt_count,
                      last_error_code, last_error_message, delivered_at, acknowledged_at, snooze_until,
                      created_at, updated_at
            """,
            (snooze_until, user_id, delivery_id),
        ).fetchone()

    def claim_due(self, worker_id: str, lease_seconds: int, limit: int) -> list[dict]:
        now = datetime.now(UTC)
        lease_until = now + timedelta(seconds=lease_seconds)
        rows = self.conn.execute(
            """
            WITH due AS (
                SELECT id
                FROM personal_affairs.reminder_deliveries
                WHERE status IN ('pending','retry_wait')
                  AND COALESCE(next_attempt_at, scheduled_for) <= now()
                ORDER BY COALESCE(next_attempt_at, scheduled_for), created_at
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE personal_affairs.reminder_deliveries d
            SET status = 'delivering', locked_by = %s, locked_until = %s,
                attempt_count = attempt_count + 1, updated_at = now()
            FROM due
            WHERE d.id = due.id
            RETURNING d.id, d.user_id, d.reminder_id, d.item_id, d.channel, d.scheduled_for,
                      d.status, d.attempt_count, d.last_error_code, d.last_error_message,
                      d.delivered_at, d.created_at, d.updated_at
            """,
            (limit, worker_id, lease_until),
        ).fetchall()
        self.conn.execute(
            """
            INSERT INTO personal_affairs.worker_heartbeats(worker_id, last_seen_at, claimed_count)
            VALUES (%s, now(), %s)
            ON CONFLICT (worker_id) DO UPDATE
            SET last_seen_at = now(), claimed_count = personal_affairs.worker_heartbeats.claimed_count + EXCLUDED.claimed_count
            """,
            (worker_id, len(rows)),
        )
        return list(rows)

    def recover_expired_leases(self) -> int:
        row = self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET status = 'retry_wait', locked_by = NULL, locked_until = NULL,
                next_attempt_at = now(), updated_at = now()
            WHERE status = 'delivering' AND locked_until < now()
            RETURNING id
            """
        ).fetchall()
        return len(row)

    def mark_delivered(self, worker_id: str, delivery_id: UUID, provider_message_id: str | None = None) -> None:
        self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET status = 'delivered', provider_message_id = %s, delivered_at = now(),
                locked_by = NULL, locked_until = NULL, updated_at = now()
            WHERE id = %s
            """,
            (provider_message_id, delivery_id),
        )
        self.conn.execute(
            """
            INSERT INTO personal_affairs.worker_heartbeats(worker_id, last_seen_at, delivered_count)
            VALUES (%s, now(), 1)
            ON CONFLICT (worker_id) DO UPDATE
            SET last_seen_at = now(), delivered_count = personal_affairs.worker_heartbeats.delivered_count + 1
            """,
            (worker_id,),
        )

    def mark_failure(
        self,
        worker_id: str,
        delivery_id: UUID,
        status: DeliveryStatus,
        error_code: str,
        error_message: str,
        next_attempt_at: datetime | None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET status = %s, last_error_code = %s, last_error_message = %s, next_attempt_at = %s,
                locked_by = NULL, locked_until = NULL, updated_at = now()
            WHERE id = %s
            """,
            (status.value, error_code, error_message[:1000], next_attempt_at, delivery_id),
        )
        self.conn.execute(
            """
            INSERT INTO personal_affairs.worker_heartbeats(worker_id, last_seen_at, failed_count)
            VALUES (%s, now(), 1)
            ON CONFLICT (worker_id) DO UPDATE
            SET last_seen_at = now(), failed_count = personal_affairs.worker_heartbeats.failed_count + 1
            """,
            (worker_id,),
        )

    def health(self) -> dict:
        row = self.conn.execute(
            """
            SELECT
              EXISTS(SELECT 1 FROM personal_affairs.worker_heartbeats WHERE last_seen_at > now() - interval '2 minutes') AS worker_seen_recently,
              COUNT(*) FILTER (WHERE status = 'pending')::int AS pending_count,
              COUNT(*) FILTER (WHERE status = 'retry_wait')::int AS retry_count,
              COUNT(*) FILTER (WHERE status = 'dead')::int AS dead_count,
              CASE
                WHEN MIN(scheduled_for) FILTER (WHERE status IN ('pending','retry_wait')) IS NULL THEN NULL
                ELSE EXTRACT(EPOCH FROM now() - MIN(scheduled_for) FILTER (WHERE status IN ('pending','retry_wait')))::int
              END AS max_lag_seconds
            FROM personal_affairs.reminder_deliveries
            WHERE status IN ('pending','retry_wait','dead')
            """
        ).fetchone()
        if row is None:
            return {
                "worker_seen_recently": False,
                "pending_count": 0,
                "retry_count": 0,
                "dead_count": 0,
                "max_lag_seconds": None,
            }
        return dict(row)

    def retry_dead(self, user_id: UUID, delivery_id: UUID) -> dict | None:
        return self.conn.execute(
            """
            UPDATE personal_affairs.reminder_deliveries
            SET status = 'pending', next_attempt_at = now(), last_error_code = NULL,
                last_error_message = NULL, updated_at = now()
            WHERE user_id = %s AND id = %s AND status = 'dead'
            RETURNING id, reminder_id, item_id, channel, scheduled_for, status, attempt_count,
                      last_error_code, last_error_message, delivered_at, acknowledged_at, snooze_until,
                      created_at, updated_at
            """,
            (user_id, delivery_id),
        ).fetchone()
