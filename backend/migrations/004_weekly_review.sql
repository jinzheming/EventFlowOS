-- WP I: weekly review feature toggle on user preferences (additive, idempotent).
-- Default off; enabling surfaces the 复盘 page in navigation.
ALTER TABLE personal_affairs.user_preferences ADD COLUMN IF NOT EXISTS weekly_review_enabled boolean NOT NULL DEFAULT false;
