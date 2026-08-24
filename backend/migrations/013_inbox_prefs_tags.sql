-- P4a: collaborator identity -> scope auto-routing rules, tag pinning for
-- sidebar shortcuts. Idempotent; safe to replay.
ALTER TABLE personal_affairs.user_preferences
    ADD COLUMN IF NOT EXISTS identity_scope_rules jsonb NOT NULL DEFAULT
    '[{"keyword":"同事","scope":"work"},{"keyword":"客户","scope":"work"},{"keyword":"供应商","scope":"work"},{"keyword":"上级","scope":"work"},{"keyword":"家人","scope":"personal"},{"keyword":"朋友","scope":"personal"}]';

ALTER TABLE personal_affairs.tags
    ADD COLUMN IF NOT EXISTS pinned boolean NOT NULL DEFAULT false;
