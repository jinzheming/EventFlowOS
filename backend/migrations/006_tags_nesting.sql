-- Tag nesting: two-level hierarchy (parent_id self-reference) plus per-parent
-- name uniqueness. Idempotent; safe to replay on every migrate run.
ALTER TABLE personal_affairs.tags ADD COLUMN IF NOT EXISTS parent_id uuid REFERENCES personal_affairs.tags(id) ON DELETE CASCADE;
ALTER TABLE personal_affairs.tags ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

-- Replace the old global (user_id, name) uniqueness with per-level uniqueness:
-- top-level names unique per user; child names unique within the same parent.
ALTER TABLE personal_affairs.tags DROP CONSTRAINT IF EXISTS tags_user_id_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS ux_tags_user_top_name ON personal_affairs.tags(user_id, name) WHERE parent_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_tags_user_parent_name ON personal_affairs.tags(user_id, parent_id, name) WHERE parent_id IS NOT NULL;
