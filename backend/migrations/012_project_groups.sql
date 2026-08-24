-- Project groups: lightweight taxonomy for project aggregation (no nesting,
-- single membership). Idempotent because the migration runner replays every
-- SQL file in order.
CREATE TABLE IF NOT EXISTS personal_affairs.project_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name text NOT NULL,
    color text NOT NULL DEFAULT '#1d4ed8',
    sort_order int NOT NULL DEFAULT 0,
    archived_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_project_groups_name_not_blank CHECK (btrim(name) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_project_groups_user_name
ON personal_affairs.project_groups(user_id, lower(btrim(name)))
WHERE archived_at IS NULL;

ALTER TABLE personal_affairs.projects
    ADD COLUMN IF NOT EXISTS group_id uuid REFERENCES personal_affairs.project_groups(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_projects_user_group
ON personal_affairs.projects(user_id, group_id);
