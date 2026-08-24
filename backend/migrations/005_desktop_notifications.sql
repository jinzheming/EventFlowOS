-- Desktop notification preference: browser-level system notifications for
-- in-app reminder deliveries. Additive, idempotent; default off.
ALTER TABLE personal_affairs.user_preferences ADD COLUMN IF NOT EXISTS desktop_notifications boolean NOT NULL DEFAULT false;
