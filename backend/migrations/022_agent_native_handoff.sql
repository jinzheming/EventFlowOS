ALTER TABLE personal_affairs.items
    ADD COLUMN IF NOT EXISTS created_by_actor text NOT NULL DEFAULT 'human' CHECK (created_by_actor IN ('human','agent','system')),
    ADD COLUMN IF NOT EXISTS updated_by_actor text NOT NULL DEFAULT 'human' CHECK (updated_by_actor IN ('human','agent','system')),
    ADD COLUMN IF NOT EXISTS source_context jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS execution_output jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS personal_affairs.agent_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    source_type text NOT NULL CHECK (source_type IN ('agent','feishu_im','tencent_meeting')),
    source_ref text,
    risk_tier text NOT NULL DEFAULT 'l2' CHECK (risk_tier IN ('l1','l2','l3')),
    confidence numeric(4,3) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','approved','edited_approved','rejected','ignored','expired')),
    proposed_action text NOT NULL DEFAULT 'create_item' CHECK (proposed_action IN ('create_item','patch_item')),
    proposed_payload jsonb NOT NULL,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason text,
    target_item_id uuid REFERENCES personal_affairs.items(id) ON DELETE SET NULL,
    applied_item_id uuid REFERENCES personal_affairs.items(id) ON DELETE SET NULL,
    expires_at timestamptz,
    decided_at timestamptz,
    decided_by_actor text CHECK (decided_by_actor IS NULL OR decided_by_actor IN ('human','agent','system')),
    decision_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_agent_proposals_user_state_created
    ON personal_affairs.agent_proposals(user_id, state, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_agent_proposals_user_target
    ON personal_affairs.agent_proposals(user_id, target_item_id)
    WHERE target_item_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS personal_affairs.agent_ingest_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    source_type text NOT NULL CHECK (source_type IN ('feishu_im')),
    tenant_key text NOT NULL,
    conversation_key text NOT NULL,
    event_id text,
    message_id text,
    sender_key text,
    payload_digest text NOT NULL,
    text_preview text,
    status text NOT NULL DEFAULT 'received' CHECK (status IN ('received','ignored','proposal_created','l1_applied','failed')),
    proposal_id uuid REFERENCES personal_affairs.agent_proposals(id) ON DELETE SET NULL,
    applied_item_id uuid REFERENCES personal_affairs.items(id) ON DELETE SET NULL,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_agent_ingest_event_identity CHECK (event_id IS NOT NULL OR message_id IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_ingest_event
    ON personal_affairs.agent_ingest_events(
        source_type,
        tenant_key,
        conversation_key,
        COALESCE(event_id, ''),
        COALESCE(message_id, '')
    );

CREATE INDEX IF NOT EXISTS ix_agent_ingest_events_user_created
    ON personal_affairs.agent_ingest_events(user_id, created_at DESC);
