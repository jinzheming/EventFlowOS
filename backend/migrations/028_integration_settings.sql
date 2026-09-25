ALTER TABLE personal_affairs.user_preferences
  ADD COLUMN IF NOT EXISTS amap_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS amap_key text,
  ADD COLUMN IF NOT EXISTS amap_default_city text,
  ADD COLUMN IF NOT EXISTS amap_timeout_seconds numeric(6,2) NOT NULL DEFAULT 3.0,
  ADD COLUMN IF NOT EXISTS tmeet_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS tmeet_bin text NOT NULL DEFAULT 'tmeet',
  ADD COLUMN IF NOT EXISTS tmeet_home text,
  ADD COLUMN IF NOT EXISTS tmeet_timeout_seconds numeric(6,2) NOT NULL DEFAULT 8.0,
  ADD COLUMN IF NOT EXISTS tmeet_allowed_commands text NOT NULL DEFAULT 'meeting:get';
INSERT INTO personal_affairs.schema_migrations(version)
VALUES ('028_integration_settings') ON CONFLICT (version) DO NOTHING;
