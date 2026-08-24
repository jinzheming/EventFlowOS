-- Habit check-ins: one row per (item, day) for recurring "habit" items.
-- Idempotent; safe to replay on every migrate run.
CREATE TABLE IF NOT EXISTS personal_affairs.habit_checkins (
    item_id uuid NOT NULL REFERENCES personal_affairs.items(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
    checkin_date date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (item_id, checkin_date)
);

CREATE INDEX IF NOT EXISTS ix_habit_checkins_user_date
ON personal_affairs.habit_checkins(user_id, checkin_date);
