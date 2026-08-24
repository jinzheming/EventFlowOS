-- WP D: waiting-context fields on items (additive, idempotent).
ALTER TABLE personal_affairs.items ADD COLUMN IF NOT EXISTS waiting_on text;
ALTER TABLE personal_affairs.items ADD COLUMN IF NOT EXISTS waiting_follow_up_date date;
