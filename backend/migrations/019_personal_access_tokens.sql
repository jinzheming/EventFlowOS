-- P9a: personal access tokens for agent-native access (additive, idempotent).
-- Multiple revocable tokens per user; only the SHA-256 hash is stored.
CREATE TABLE IF NOT EXISTS personal_affairs.personal_access_tokens (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name         text NOT NULL,
    token_hash   text NOT NULL UNIQUE,
    scopes       text[] NOT NULL DEFAULT '{read,write}',
    expires_at   timestamptz,
    last_used_at timestamptz,
    revoked_at   timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_pat_name_not_blank CHECK (btrim(name) <> '')
);

CREATE INDEX IF NOT EXISTS ix_personal_access_tokens_user
    ON personal_affairs.personal_access_tokens(user_id);
