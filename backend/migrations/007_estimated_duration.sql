-- Optional estimated duration per item (minutes). Idempotent.
ALTER TABLE personal_affairs.items ADD COLUMN IF NOT EXISTS estimated_minutes integer
  CHECK (estimated_minutes IS NULL OR estimated_minutes BETWEEN 1 AND 10080);
