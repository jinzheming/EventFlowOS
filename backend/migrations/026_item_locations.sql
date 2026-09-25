ALTER TABLE personal_affairs.items
  ADD COLUMN IF NOT EXISTS location_name text,
  ADD COLUMN IF NOT EXISTS location_address text,
  ADD COLUMN IF NOT EXISTS location_provider text,
  ADD COLUMN IF NOT EXISTS location_poi_id text,
  ADD COLUMN IF NOT EXISTS location_latitude double precision,
  ADD COLUMN IF NOT EXISTS location_longitude double precision,
  ADD COLUMN IF NOT EXISTS location_confidence numeric(5,4),
  ADD COLUMN IF NOT EXISTS location_updated_at timestamptz;
INSERT INTO personal_affairs.schema_migrations(version)
VALUES ('026_item_locations')
ON CONFLICT (version) DO NOTHING;
