-- 029: drop legacy integration tables superseded by 028_integration_settings.
--
-- The earlier "agent native handoff" line shipped two parallel profile/binding
-- pairs (llm_* and external_*, plus write_targets). 028_integration_settings
-- moved the surviving settings onto personal_affairs.user_preferences, so these
-- five tables have been dead weight since then: every one of them still holds
-- zero rows and no code path in backend/src or frontend/src references them.
--
-- Child tables are dropped before their parents so no CASCADE is required.

DROP TABLE IF EXISTS personal_affairs.write_targets;
DROP TABLE IF EXISTS personal_affairs.llm_bindings;
DROP TABLE IF EXISTS personal_affairs.llm_profiles;
DROP TABLE IF EXISTS personal_affairs.external_bindings;
DROP TABLE IF EXISTS personal_affairs.external_profiles;

-- These five versions were recorded by migrations that were later renumbered or
-- rolled into other files. No .sql file maps to them any more, so they only
-- pollute the applied-version ledger.
DELETE FROM personal_affairs.schema_migrations
 WHERE version IN (
   '023_item_history_indexes',
   '024_write_targets',
   '025_llm_profiles',
   '026_external_profiles',
   '027_event_location'
 );

INSERT INTO personal_affairs.schema_migrations(version)
VALUES ('029_drop_legacy_tables') ON CONFLICT (version) DO NOTHING;
