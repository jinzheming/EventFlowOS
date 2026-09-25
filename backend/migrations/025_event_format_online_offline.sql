-- Normalize legacy hybrid events and enforce one activity form.
DO $$
DECLARE c record;
BEGIN
  FOR c IN
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'personal_affairs.items'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%event_format%'
  LOOP
    EXECUTE format('ALTER TABLE personal_affairs.items DROP CONSTRAINT %I', c.conname);
  END LOOP;
END $$;
INSERT INTO personal_affairs.schema_migrations(version)
VALUES ('025_event_format_online_offline')
ON CONFLICT (version) DO NOTHING;
UPDATE personal_affairs.items
SET event_format = CASE
  WHEN event_format = 'hybrid' AND NULLIF(event_url, '') IS NOT NULL THEN 'online'
  WHEN event_format = 'hybrid' AND NULLIF(event_location, '') IS NOT NULL THEN 'offline'
  ELSE NULL
END,
event_location = CASE WHEN event_format = 'online' OR (event_format = 'hybrid' AND NULLIF(event_url, '') IS NOT NULL) THEN NULL ELSE event_location END,
event_url = CASE WHEN event_format = 'offline' OR (event_format = 'hybrid' AND NULLIF(event_url, '') IS NULL) THEN NULL ELSE event_url END,
notes = CASE WHEN event_format = 'hybrid' AND NULLIF(event_location, '') IS NOT NULL AND NULLIF(event_url, '') IS NOT NULL
  THEN concat_ws(E'\n', notes, '迁移保留的线下地点：' || event_location) ELSE notes END
WHERE event_format = 'hybrid' OR (event_format = 'online' AND event_location IS NOT NULL) OR (event_format = 'offline' AND event_url IS NOT NULL);
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'items_event_format_check') THEN
    ALTER TABLE personal_affairs.items ADD CONSTRAINT items_event_format_check CHECK (event_format IS NULL OR event_format IN ('online','offline'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'items_event_format_fields_check') THEN
    ALTER TABLE personal_affairs.items ADD CONSTRAINT items_event_format_fields_check CHECK (
    event_format IS NULL OR (event_format = 'online' AND event_location IS NULL) OR
    (event_format = 'offline' AND event_url IS NULL)
    );
  END IF;
END $$;
