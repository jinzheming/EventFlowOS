-- WP F: minimal recurrence rule on items (additive, idempotent).
-- Materialization happens on completion: the next occurrence is created as a
-- new item carrying the same rule with a decremented count.
ALTER TABLE personal_affairs.items ADD COLUMN IF NOT EXISTS recurrence_freq text;
ALTER TABLE personal_affairs.items ADD COLUMN IF NOT EXISTS recurrence_interval integer;
ALTER TABLE personal_affairs.items ADD COLUMN IF NOT EXISTS recurrence_until date;
ALTER TABLE personal_affairs.items ADD COLUMN IF NOT EXISTS recurrence_count integer;
