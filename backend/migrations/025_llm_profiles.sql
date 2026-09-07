-- User-configurable LLM profiles and purpose bindings.
-- Secrets stay outside business config; auth_ref points at runtime/gateway secrets.
CREATE TABLE IF NOT EXISTS personal_affairs.llm_profiles (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name           text NOT NULL,
    provider_key   text NOT NULL DEFAULT 'litellm',
    preset_key     text,
    base_url       text,
    model_name     text NOT NULL,
    auth_ref       text,
    capabilities   jsonb NOT NULL DEFAULT '{}'::jsonb,
    default_params jsonb NOT NULL DEFAULT '{}'::jsonb,
    privacy_tier   text NOT NULL DEFAULT 'standard',
    active         boolean NOT NULL DEFAULT true,
    priority       integer NOT NULL DEFAULT 100,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_llm_profiles_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_llm_profiles_model_not_blank CHECK (btrim(model_name) <> ''),
    CONSTRAINT ck_llm_profiles_provider CHECK (provider_key IN ('litellm', 'openai_compatible', 'ollama', 'custom')),
    CONSTRAINT ck_llm_profiles_privacy CHECK (privacy_tier IN ('standard', 'private', 'sensitive')),
    CONSTRAINT ck_llm_profiles_capabilities_object CHECK (jsonb_typeof(capabilities) = 'object'),
    CONSTRAINT ck_llm_profiles_params_object CHECK (jsonb_typeof(default_params) = 'object'),
    CONSTRAINT ck_llm_profiles_priority CHECK (priority >= 0 AND priority <= 10000)
);

CREATE TABLE IF NOT EXISTS personal_affairs.llm_bindings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    purpose_key     text NOT NULL,
    scope_type      text NOT NULL DEFAULT 'global',
    scope_value     text,
    profile_id      uuid NOT NULL REFERENCES personal_affairs.llm_profiles(id) ON DELETE CASCADE,
    override_params jsonb NOT NULL DEFAULT '{}'::jsonb,
    instructions    text,
    active          boolean NOT NULL DEFAULT true,
    priority        integer NOT NULL DEFAULT 100,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_llm_bindings_purpose_not_blank CHECK (btrim(purpose_key) <> ''),
    CONSTRAINT ck_llm_bindings_scope CHECK (scope_type IN ('global', 'project', 'source_type', 'item_type', 'risk_tier')),
    CONSTRAINT ck_llm_bindings_global_scope CHECK (scope_type <> 'global' OR scope_value IS NULL),
    CONSTRAINT ck_llm_bindings_params_object CHECK (jsonb_typeof(override_params) = 'object'),
    CONSTRAINT ck_llm_bindings_priority CHECK (priority >= 0 AND priority <= 10000)
);

CREATE INDEX IF NOT EXISTS ix_llm_profiles_user
    ON personal_affairs.llm_profiles(user_id);

CREATE INDEX IF NOT EXISTS ix_llm_profiles_active_user
    ON personal_affairs.llm_profiles(user_id, active, priority)
    WHERE active = true;

CREATE INDEX IF NOT EXISTS ix_llm_bindings_user_purpose
    ON personal_affairs.llm_bindings(user_id, purpose_key, active, priority);

CREATE INDEX IF NOT EXISTS ix_llm_bindings_profile
    ON personal_affairs.llm_bindings(profile_id);
