-- General external capability profiles and bindings.
-- This lifts write_targets into a broader profile/binding model while keeping
-- the v0 write_targets table and API available for compatibility.
CREATE TABLE IF NOT EXISTS personal_affairs.external_profiles (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name         text NOT NULL,
    provider_key text NOT NULL,
    preset_key   text,
    capability   text NOT NULL,
    auth_ref     text,
    source_ref   text,
    active       boolean NOT NULL DEFAULT true,
    priority     integer NOT NULL DEFAULT 100,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_external_profiles_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_external_profiles_provider CHECK (provider_key IN ('feishu', 'webhook', 'notion', 'calendar', 'custom_http')),
    CONSTRAINT ck_external_profiles_capability CHECK (capability IN ('write', 'read', 'sync', 'notify', 'lookup', 'export')),
    CONSTRAINT ck_external_profiles_priority CHECK (priority >= 0 AND priority <= 10000)
);

CREATE TABLE IF NOT EXISTS personal_affairs.external_bindings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    profile_id      uuid NOT NULL REFERENCES personal_affairs.external_profiles(id) ON DELETE CASCADE,
    purpose_key     text NOT NULL,
    scope_type      text NOT NULL DEFAULT 'global',
    scope_value     text,
    target_ref      text NOT NULL,
    format_key      text NOT NULL,
    field_mapping   jsonb NOT NULL DEFAULT '{}'::jsonb,
    value_mapping   jsonb NOT NULL DEFAULT '{}'::jsonb,
    instructions    text,
    conflict_policy text NOT NULL DEFAULT 'ask',
    dry_run         boolean NOT NULL DEFAULT false,
    active          boolean NOT NULL DEFAULT true,
    priority        integer NOT NULL DEFAULT 100,
    last_used_at    timestamptz,
    last_error      text,
    source_ref      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_external_bindings_purpose_not_blank CHECK (btrim(purpose_key) <> ''),
    CONSTRAINT ck_external_bindings_target_not_blank CHECK (btrim(target_ref) <> ''),
    CONSTRAINT ck_external_bindings_scope CHECK (scope_type IN ('global', 'project', 'item_type', 'source_type', 'person', 'tag')),
    CONSTRAINT ck_external_bindings_global_scope CHECK (scope_type <> 'global' OR scope_value IS NULL),
    CONSTRAINT ck_external_bindings_format CHECK (format_key IN ('feishu_bitable_item_v1', 'custom_json_v1', 'webhook_notification_v1', 'calendar_event_v1', 'notion_database_item_v1')),
    CONSTRAINT ck_external_bindings_field_mapping_object CHECK (jsonb_typeof(field_mapping) = 'object'),
    CONSTRAINT ck_external_bindings_value_mapping_object CHECK (jsonb_typeof(value_mapping) = 'object'),
    CONSTRAINT ck_external_bindings_conflict CHECK (conflict_policy IN ('append', 'update', 'skip', 'ask')),
    CONSTRAINT ck_external_bindings_priority CHECK (priority >= 0 AND priority <= 10000)
);

CREATE INDEX IF NOT EXISTS ix_external_profiles_user
    ON personal_affairs.external_profiles(user_id);

CREATE INDEX IF NOT EXISTS ix_external_profiles_active_user
    ON personal_affairs.external_profiles(user_id, capability, active, priority)
    WHERE active = true;

CREATE UNIQUE INDEX IF NOT EXISTS ux_external_profiles_source_ref
    ON personal_affairs.external_profiles(user_id, source_ref)
    WHERE source_ref IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_external_bindings_user_purpose
    ON personal_affairs.external_bindings(user_id, purpose_key, active, priority);

CREATE INDEX IF NOT EXISTS ix_external_bindings_profile
    ON personal_affairs.external_bindings(profile_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_external_bindings_source_ref
    ON personal_affairs.external_bindings(user_id, source_ref)
    WHERE source_ref IS NOT NULL;

INSERT INTO personal_affairs.external_profiles(
    user_id, name, provider_key, preset_key, capability, auth_ref, source_ref, active, priority, created_at, updated_at
)
SELECT
    wt.user_id,
    wt.name,
    CASE wt.target_type WHEN 'feishu_bitable' THEN 'feishu' ELSE 'custom_http' END,
    wt.target_type,
    'write',
    'runtime_external',
    'write_target:' || wt.id::text,
    wt.active,
    100,
    wt.created_at,
    wt.updated_at
FROM personal_affairs.write_targets wt
WHERE NOT EXISTS (
    SELECT 1
    FROM personal_affairs.external_profiles ep
    WHERE ep.user_id = wt.user_id AND ep.source_ref = 'write_target:' || wt.id::text
);

INSERT INTO personal_affairs.external_bindings(
    user_id, profile_id, purpose_key, scope_type, scope_value, target_ref, format_key,
    field_mapping, value_mapping, instructions, conflict_policy, dry_run, active,
    priority, source_ref, created_at, updated_at
)
SELECT
    wt.user_id,
    ep.id,
    'item_write',
    'global',
    NULL,
    wt.target_url,
    wt.format_key,
    wt.field_mapping,
    '{}'::jsonb,
    wt.instructions,
    CASE wt.target_type WHEN 'feishu_bitable' THEN 'append' ELSE 'ask' END,
    false,
    wt.active,
    100,
    'write_target:' || wt.id::text,
    wt.created_at,
    wt.updated_at
FROM personal_affairs.write_targets wt
JOIN personal_affairs.external_profiles ep
  ON ep.user_id = wt.user_id
 AND ep.source_ref = 'write_target:' || wt.id::text
WHERE NOT EXISTS (
    SELECT 1
    FROM personal_affairs.external_bindings eb
    WHERE eb.user_id = wt.user_id AND eb.source_ref = 'write_target:' || wt.id::text
);
