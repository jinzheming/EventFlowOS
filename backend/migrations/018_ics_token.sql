-- ICS feed: per-user read-only feed token. Idempotent; safe to replay.
ALTER TABLE personal_affairs.user_preferences
    ADD COLUMN IF NOT EXISTS ics_token text;
