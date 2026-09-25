CREATE TABLE IF NOT EXISTS personal_affairs.item_relations (
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    predecessor_item_id uuid NOT NULL REFERENCES personal_affairs.items(id) ON DELETE CASCADE,
    successor_item_id uuid NOT NULL REFERENCES personal_affairs.items(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (predecessor_item_id, successor_item_id),
    CONSTRAINT ck_item_relation_not_self CHECK (predecessor_item_id <> successor_item_id)
);

CREATE INDEX IF NOT EXISTS ix_item_relations_successor
    ON personal_affairs.item_relations(user_id, successor_item_id);
CREATE INDEX IF NOT EXISTS ix_item_relations_predecessor
    ON personal_affairs.item_relations(user_id, predecessor_item_id);

INSERT INTO personal_affairs.schema_migrations(version)
VALUES ('024_item_relations')
ON CONFLICT (version) DO NOTHING;
