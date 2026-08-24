CREATE SCHEMA IF NOT EXISTS personal_affairs;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE IF NOT EXISTS personal_affairs.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS personal_affairs.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username citext NOT NULL UNIQUE,
    password_hash text NOT NULL,
    timezone text NOT NULL DEFAULT 'Asia/Shanghai',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS personal_affairs.sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    csrf_token text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_sessions_user_expires ON personal_affairs.sessions(user_id, expires_at);

CREATE TABLE IF NOT EXISTS personal_affairs.user_preferences (
    user_id uuid PRIMARY KEY REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    timezone text NOT NULL DEFAULT 'Asia/Shanghai',
    work_filters jsonb NOT NULL DEFAULT '{}'::jsonb,
    personal_filters jsonb NOT NULL DEFAULT '{}'::jsonb,
    calendar_filters jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS personal_affairs.projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name text NOT NULL,
    goal text,
    status text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','active','on_hold','completed','cancelled')),
    health text NOT NULL DEFAULT 'unknown' CHECK (health IN ('unknown','on_track','at_risk','blocked')),
    progress_mode text NOT NULL DEFAULT 'manual' CHECK (progress_mode IN ('manual','milestone')),
    progress_percent integer CHECK (progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100),
    risk_summary text,
    next_step text,
    next_review_at timestamptz,
    due_date date,
    color text NOT NULL DEFAULT '#2563EB',
    archived_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_projects_user_status ON personal_affairs.projects(user_id, status, archived_at);

CREATE TABLE IF NOT EXISTS personal_affairs.milestones (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES personal_affairs.projects(id) ON DELETE CASCADE,
    title text NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','done','cancelled')),
    due_date date,
    weight integer NOT NULL DEFAULT 1 CHECK (weight >= 0),
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_milestones_project_due ON personal_affairs.milestones(project_id, due_date);

CREATE TABLE IF NOT EXISTS personal_affairs.project_updates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES personal_affairs.projects(id) ON DELETE CASCADE,
    body text NOT NULL,
    health text CHECK (health IS NULL OR health IN ('unknown','on_track','at_risk','blocked')),
    progress_percent integer CHECK (progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100),
    risk_summary text,
    next_step text,
    corrects_update_id uuid REFERENCES personal_affairs.project_updates(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_project_updates_project_created ON personal_affairs.project_updates(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS personal_affairs.items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    scope text NOT NULL CHECK (scope IN ('work','personal')),
    project_id uuid REFERENCES personal_affairs.projects(id) ON DELETE SET NULL,
    title text NOT NULL,
    notes text,
    status text NOT NULL DEFAULT 'inbox' CHECK (status IN ('inbox','planned','in_progress','waiting','done','cancelled')),
    priority text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
    all_day boolean NOT NULL DEFAULT true,
    start_at timestamptz,
    due_at timestamptz,
    start_date date,
    due_date date,
    completed_at timestamptz,
    cancelled_at timestamptz,
    archived_at timestamptz,
    sort_order integer NOT NULL DEFAULT 0,
    version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_personal_items_no_project CHECK (scope <> 'personal' OR project_id IS NULL),
    CONSTRAINT ck_item_schedule_shape CHECK (
        (all_day = true AND start_at IS NULL AND due_at IS NULL)
        OR
        (all_day = false AND start_date IS NULL AND due_date IS NULL)
    ),
    CONSTRAINT ck_item_schedule_order CHECK (
        (start_at IS NULL OR due_at IS NULL OR start_at <= due_at)
        AND
        (start_date IS NULL OR due_date IS NULL OR start_date <= due_date)
    )
);

CREATE INDEX IF NOT EXISTS ix_items_user_scope_status ON personal_affairs.items(user_id, scope, status, archived_at);
CREATE INDEX IF NOT EXISTS ix_items_user_due ON personal_affairs.items(user_id, due_date, due_at) WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_items_user_project ON personal_affairs.items(user_id, project_id) WHERE project_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS personal_affairs.tags (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name citext NOT NULL,
    color text NOT NULL DEFAULT '#64748B',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS personal_affairs.item_tags (
    item_id uuid NOT NULL REFERENCES personal_affairs.items(id) ON DELETE CASCADE,
    tag_id uuid NOT NULL REFERENCES personal_affairs.tags(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, tag_id)
);

CREATE TABLE IF NOT EXISTS personal_affairs.reminders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    item_id uuid NOT NULL REFERENCES personal_affairs.items(id) ON DELETE CASCADE,
    timing text NOT NULL DEFAULT 'before_due' CHECK (timing IN ('at_start','before_start','before_due')),
    offset_minutes integer NOT NULL DEFAULT 10 CHECK (offset_minutes >= 0),
    timezone text NOT NULL DEFAULT 'Asia/Shanghai',
    external_enabled boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_reminder_item ON personal_affairs.reminders(item_id) WHERE active = true;

CREATE TABLE IF NOT EXISTS personal_affairs.reminder_deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    reminder_id uuid NOT NULL REFERENCES personal_affairs.reminders(id) ON DELETE CASCADE,
    item_id uuid NOT NULL REFERENCES personal_affairs.items(id) ON DELETE CASCADE,
    channel text NOT NULL CHECK (channel IN ('in_app','feishu','ntfy')),
    scheduled_for timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','delivering','delivered','retry_wait','dead','cancelled')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    locked_by text,
    locked_until timestamptz,
    next_attempt_at timestamptz,
    provider_message_id text,
    provider_status text,
    last_error_code text,
    last_error_message text,
    delivered_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (reminder_id, scheduled_for, channel)
);

CREATE INDEX IF NOT EXISTS ix_deliveries_due_claim ON personal_affairs.reminder_deliveries(status, next_attempt_at, scheduled_for)
    WHERE status IN ('pending','retry_wait');
CREATE INDEX IF NOT EXISTS ix_deliveries_user_status ON personal_affairs.reminder_deliveries(user_id, status, scheduled_for DESC);

CREATE TABLE IF NOT EXISTS personal_affairs.worker_heartbeats (
    worker_id text PRIMARY KEY,
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    claimed_count bigint NOT NULL DEFAULT 0,
    delivered_count bigint NOT NULL DEFAULT 0,
    failed_count bigint NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS personal_affairs.activity_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    action text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_activity_user_entity ON personal_affairs.activity_events(user_id, entity_type, entity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS personal_affairs.create_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    client_request_id text NOT NULL,
    create_request_hash text NOT NULL,
    resource_type text NOT NULL,
    resource_id uuid NOT NULL,
    response_snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, client_request_id, resource_type)
);

INSERT INTO personal_affairs.schema_migrations(version)
VALUES ('001_initial')
ON CONFLICT (version) DO NOTHING;
