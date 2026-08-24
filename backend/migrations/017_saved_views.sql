-- Smart views: saved filter combinations surfaced as sidebar shortcuts.
-- Idempotent; safe to replay on every migrate run.
CREATE TABLE IF NOT EXISTS personal_affairs.saved_views (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name text NOT NULL,
    spec jsonb NOT NULL DEFAULT '{}',
    sort_order int NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_saved_views_name_not_blank CHECK (btrim(name) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_saved_views_user_name
ON personal_affairs.saved_views(user_id, lower(btrim(name)));
