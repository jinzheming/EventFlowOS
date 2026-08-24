-- WP J: server-side ack/snooze for reminder deliveries (additive, idempotent).
-- acknowledged_at = user dismissed; snooze_until = hidden until this instant.
ALTER TABLE personal_affairs.reminder_deliveries ADD COLUMN IF NOT EXISTS acknowledged_at timestamptz;
ALTER TABLE personal_affairs.reminder_deliveries ADD COLUMN IF NOT EXISTS snooze_until timestamptz;
CREATE INDEX IF NOT EXISTS ix_deliveries_user_unseen
  ON personal_affairs.reminder_deliveries(user_id, scheduled_for)
  WHERE status = 'delivered' AND acknowledged_at IS NULL;
