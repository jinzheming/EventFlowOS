CREATE INDEX IF NOT EXISTS ix_items_history_done
  ON personal_affairs.items (
    user_id,
    scope,
    (COALESCE(completed_at, updated_at)) DESC,
    updated_at DESC,
    title ASC,
    id ASC
  )
  WHERE deleted_at IS NULL AND archived_at IS NULL AND status = 'done';

CREATE INDEX IF NOT EXISTS ix_items_history_archived
  ON personal_affairs.items (
    user_id,
    scope,
    (CASE WHEN status = 'done' THEN COALESCE(completed_at, archived_at, updated_at) ELSE COALESCE(archived_at, updated_at) END) DESC,
    updated_at DESC,
    title ASC,
    id ASC
  )
  WHERE deleted_at IS NULL AND archived_at IS NOT NULL;
