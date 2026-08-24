-- P9b: outbound webhook subscriptions (additive, idempotent).
CREATE TABLE IF NOT EXISTS personal_affairs.webhook_subscriptions (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name       text NOT NULL,
    url        text NOT NULL,
    secret     text NOT NULL,
    events     text[] NOT NULL,
    active     boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_webhook_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_webhook_url_not_blank CHECK (btrim(url) <> '')
);

CREATE INDEX IF NOT EXISTS ix_webhook_subscriptions_user
    ON personal_affairs.webhook_subscriptions(user_id);
