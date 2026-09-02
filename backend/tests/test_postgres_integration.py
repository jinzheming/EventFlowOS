import os
from collections.abc import Iterator
from uuid import UUID

import psycopg
import pytest
from psycopg.rows import dict_row

from personal_affairs.domain.enums import ItemScope
from personal_affairs.storage.migrations import MIGRATIONS_DIR, run_migrations
from personal_affairs.storage.repositories.event_outbox import EventOutboxRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.webhooks import (
    WebhookSubscriptionsRepository,
    generate_webhook_secret,
)

DATABASE_URL = os.environ.get("PERSONAL_AFFAIRS_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="set PERSONAL_AFFAIRS_TEST_DATABASE_URL to run PostgreSQL integration tests",
)


def reset_database(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        TRUNCATE TABLE
          personal_affairs.agent_ingest_events,
          personal_affairs.agent_proposals,
          personal_affairs.digest_log,
          personal_affairs.saved_views,
          personal_affairs.focus_sessions,
          personal_affairs.habit_checkins,
          personal_affairs.push_subscriptions,
          personal_affairs.personal_access_tokens,
          personal_affairs.sessions,
          personal_affairs.create_requests,
          personal_affairs.activity_events,
          personal_affairs.reminder_deliveries,
          personal_affairs.reminders,
          personal_affairs.event_outbox,
          personal_affairs.webhook_subscriptions,
          personal_affairs.webhook_worker_heartbeats,
          personal_affairs.item_people,
          personal_affairs.item_tags,
          personal_affairs.items,
          personal_affairs.milestones,
          personal_affairs.project_updates,
          personal_affairs.projects,
          personal_affairs.project_groups,
          personal_affairs.tags,
          personal_affairs.people,
          personal_affairs.user_preferences,
          personal_affairs.users
        RESTART IDENTITY CASCADE
        """
    )
    conn.commit()


@pytest.fixture
def pg_conn() -> Iterator[psycopg.Connection]:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        reset_database(conn)
        yield conn
        reset_database(conn)


def create_user(conn: psycopg.Connection, username: str = "integration") -> UUID:
    row = conn.execute(
        """
        INSERT INTO personal_affairs.users(username, password_hash, timezone)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (username, "not-a-real-password-hash", "Asia/Shanghai"),
    ).fetchone()
    assert row is not None
    return row["id"]


def test_migrations_are_idempotent(pg_conn: psycopg.Connection) -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    versions = [
        row["version"]
        for row in pg_conn.execute(
            "SELECT version FROM personal_affairs.schema_migrations ORDER BY version"
        ).fetchall()
    ]
    expected_versions = [path.stem for path in sorted(MIGRATIONS_DIR.glob("*.sql"))]

    assert "023_webhook_worker_heartbeats" in versions
    assert len(versions) == len(set(versions))
    assert set(expected_versions) <= set(versions)


def test_item_soft_delete_restore_roundtrip(pg_conn: psycopg.Connection) -> None:
    user_id = create_user(pg_conn)
    repo = ItemsRepository(pg_conn)
    item = repo.create_item(user_id, {"scope": "work", "title": "Integration task", "status": "planned"})

    assert repo.list_items(user_id, ItemScope.WORK)[0]["id"] == item["id"]
    assert repo.soft_delete(user_id, item["id"]) is not None
    pg_conn.commit()
    assert repo.list_items(user_id, ItemScope.WORK) == []
    assert repo.list_items(user_id, ItemScope.WORK, deleted=True)[0]["id"] == item["id"]

    restored = repo.restore_deleted(user_id, item["id"])
    pg_conn.commit()

    assert restored is not None
    assert restored["deleted_at"] is None
    assert repo.list_items(user_id, ItemScope.WORK)[0]["id"] == item["id"]


def test_webhook_subscription_and_outbox_health(pg_conn: psycopg.Connection) -> None:
    user_id = create_user(pg_conn)
    item = ItemsRepository(pg_conn).create_item(
        user_id,
        {"scope": "work", "title": "Publish integration event", "status": "planned"},
    )
    webhook_repo = WebhookSubscriptionsRepository(pg_conn)
    outbox_repo = EventOutboxRepository(pg_conn)

    secret = generate_webhook_secret()
    subscription = webhook_repo.create(
        user_id,
        "local test",
        "https://example.com/hook",
        ["item.created"],
        secret,
    )
    outbox_repo.record(user_id, "item.created", "item", item["id"], {"title": item["title"]})
    pg_conn.commit()

    assert webhook_repo.list_active_for_event(user_id, "item.created")[0]["id"] == subscription["id"]
    assert outbox_repo.health(user_id)["pending_count"] == 1

    claimed = outbox_repo.claim_batch("webhook:test", 60, 10)
    assert len(claimed) == 1
    outbox_repo.record_webhook_heartbeat("webhook:test", claimed_count=1)
    outbox_repo.mark_failure(claimed[0]["id"], claimed[0]["attempt_count"], None, "DEAD:HTTP_500", "failed")
    outbox_repo.record_webhook_heartbeat("webhook:test", failed_count=1)
    pg_conn.commit()

    health = outbox_repo.health(user_id)
    assert health["worker_seen_recently"] is True
    assert health["dead_count"] == 1
    assert health["retry_count"] == 0
