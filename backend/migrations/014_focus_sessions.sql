-- Focus timer: append-only focus session log per item. Idempotent; safe to
-- replay on every migrate run.
CREATE TABLE IF NOT EXISTS personal_affairs.focus_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    item_id uuid NOT NULL REFERENCES personal_affairs.items(id) ON DELETE CASCADE,
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    duration_seconds int,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_focus_sessions_active
ON personal_affairs.focus_sessions(user_id)
WHERE ended_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_focus_sessions_user_item
ON personal_affairs.focus_sessions(user_id, item_id);

CREATE INDEX IF NOT EXISTS ix_focus_sessions_user_started
ON personal_affairs.focus_sessions(user_id, started_at);
