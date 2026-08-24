-- WP L: recycle bin — soft delete for items (additive, idempotent).
ALTER TABLE personal_affairs.items ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
CREATE INDEX IF NOT EXISTS ix_items_user_deleted
  ON personal_affairs.items(user_id, deleted_at)
  WHERE deleted_at IS NOT NULL;
