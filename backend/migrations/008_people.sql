-- People directory and item-person relationships. Idempotent because the
-- migration runner replays every SQL file in order.
CREATE TABLE IF NOT EXISTS personal_affairs.people (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    name text NOT NULL,
    identity text,
    note text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_people_name_not_blank CHECK (btrim(name) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_people_user_name_identity
ON personal_affairs.people(user_id, lower(btrim(name)), COALESCE(lower(btrim(identity)), ''));

CREATE TABLE IF NOT EXISTS personal_affairs.item_people (
    item_id uuid NOT NULL REFERENCES personal_affairs.items(id) ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES personal_affairs.people(id) ON DELETE RESTRICT,
    role text NOT NULL CHECK (role IN ('together','waiting')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (item_id, person_id)
);

CREATE INDEX IF NOT EXISTS ix_item_people_person ON personal_affairs.item_people(person_id);
CREATE INDEX IF NOT EXISTS ix_item_people_item_role ON personal_affairs.item_people(item_id, role);

-- Backfill legacy waiting_on text into the new canonical people tables.
WITH legacy AS (
    SELECT id AS item_id, user_id, btrim(waiting_on) AS name
    FROM personal_affairs.items
    WHERE waiting_on IS NOT NULL AND btrim(waiting_on) <> ''
), inserted_people AS (
    INSERT INTO personal_affairs.people(user_id, name, identity, note)
    SELECT DISTINCT user_id, name, NULL, '由旧等待对象迁移'
    FROM legacy
    ON CONFLICT (user_id, lower(btrim(name)), COALESCE(lower(btrim(identity)), '')) DO UPDATE
    SET updated_at = personal_affairs.people.updated_at
    RETURNING id, user_id, name
)
INSERT INTO personal_affairs.item_people(item_id, person_id, role)
SELECT l.item_id, p.id, 'waiting'
FROM legacy l
JOIN personal_affairs.people p
  ON p.user_id = l.user_id
 AND lower(btrim(p.name)) = lower(l.name)
 AND p.identity IS NULL
ON CONFLICT (item_id, person_id) DO UPDATE
SET role = EXCLUDED.role, updated_at = now();
