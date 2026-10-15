-- Add online/offline event details to scheduled items. Idempotent because the
-- migration runner replays every SQL file in order.
ALTER TABLE personal_affairs.items
    ADD COLUMN IF NOT EXISTS event_format text CHECK (event_format IS NULL OR event_format IN ('online','offline','hybrid')),
    ADD COLUMN IF NOT EXISTS event_location text,
    ADD COLUMN IF NOT EXISTS event_url text;
