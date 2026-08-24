-- P6b: morning/evening digest preferences + send log (one row per user/kind/day).
-- Idempotent; safe to replay on every migrate run.
ALTER TABLE personal_affairs.user_preferences
    ADD COLUMN IF NOT EXISTS digest_morning_enabled boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS digest_evening_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS digest_morning_time text NOT NULL DEFAULT '08:00',
    ADD COLUMN IF NOT EXISTS digest_evening_time text NOT NULL DEFAULT '21:00';

CREATE TABLE IF NOT EXISTS personal_affairs.digest_log (
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('morning', 'evening')),
    sent_on date NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, kind, sent_on)
);
