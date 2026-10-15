-- Extensible write targets for agents and external automation.
-- Stores user-owned destination links and output format instructions; secrets
-- remain outside the application runtime.
CREATE TABLE IF NOT EXISTS personal_affairs.write_targets (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name          text NOT NULL,
    target_type   text NOT NULL DEFAULT 'feishu_bitable',
    target_url    text NOT NULL,
    format_key    text NOT NULL DEFAULT 'feishu_bitable_item_v1',
    field_mapping jsonb NOT NULL DEFAULT '{}'::jsonb,
    instructions  text,
    active        boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_write_targets_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_write_targets_url_not_blank CHECK (btrim(target_url) <> ''),
    CONSTRAINT ck_write_targets_type CHECK (target_type IN ('feishu_bitable', 'custom')),
    CONSTRAINT ck_write_targets_format CHECK (format_key IN ('feishu_bitable_item_v1', 'compact_item_v1', 'custom_json_v1')),
    CONSTRAINT ck_write_targets_mapping_object CHECK (jsonb_typeof(field_mapping) = 'object')
);

CREATE INDEX IF NOT EXISTS ix_write_targets_user
    ON personal_affairs.write_targets(user_id);

CREATE INDEX IF NOT EXISTS ix_write_targets_active_user
    ON personal_affairs.write_targets(user_id, active)
    WHERE active = true;
