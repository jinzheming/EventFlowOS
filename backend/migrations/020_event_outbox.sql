-- P9b: event outbox for outbound webhook dispatch (additive, idempotent).
-- Events are written in the same transaction as the business change
-- (at-least-once); the webhook publisher claims due events with a lease,
-- mirrors the reminder worker's retry/backoff/dead semantics.
CREATE TABLE IF NOT EXISTS personal_affairs.event_outbox (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid NOT NULL,
    event_type        text NOT NULL,
    aggregate         text NOT NULL,
    aggregate_id      uuid NOT NULL,
    payload           jsonb NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    claimed_at        timestamptz,
    claimed_by        text,
    attempt_count     integer NOT NULL DEFAULT 0,
    retry_at          timestamptz,
    published_at      timestamptz,
    last_error_code   text,
    last_error_message text
);

CREATE INDEX IF NOT EXISTS idx_event_outbox_claim
    ON personal_affairs.event_outbox (created_at)
    WHERE published_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_event_outbox_user
    ON personal_affairs.event_outbox(user_id);
