-- P9c: webhook publisher observability for self-hosted operators.
CREATE TABLE IF NOT EXISTS personal_affairs.webhook_worker_heartbeats (
    worker_id text PRIMARY KEY,
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    claimed_count bigint NOT NULL DEFAULT 0,
    published_count bigint NOT NULL DEFAULT 0,
    failed_count bigint NOT NULL DEFAULT 0
);

INSERT INTO personal_affairs.schema_migrations(version)
VALUES ('023_webhook_worker_heartbeats')
ON CONFLICT (version) DO NOTHING;
