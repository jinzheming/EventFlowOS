from copy import copy
from uuid import UUID

from personal_affairs.config import Settings
from personal_affairs.storage.repositories.preferences import PreferencesRepository


def settings_for_user(conn, user_id: UUID, cfg: Settings) -> Settings:
    """Overlay per-user integration settings while retaining environment defaults."""
    row = PreferencesRepository(conn).get(user_id, cfg.default_timezone)
    resolved = copy(cfg)
    if row.get("amap_key_configured"):
        resolved.amap_enabled = bool(row.get("amap_enabled"))
        # The repository intentionally masks the key; fetch it only for server-side use.
        secret = conn.execute("SELECT amap_key FROM personal_affairs.user_preferences WHERE user_id = %s", (user_id,)).fetchone()
        resolved.amap_key = secret["amap_key"] if secret else cfg.amap_key
    resolved.amap_default_city = row.get("amap_default_city") or cfg.amap_default_city
    resolved.amap_timeout_seconds = float(row.get("amap_timeout_seconds") or cfg.amap_timeout_seconds)
    resolved.tmeet_enabled = bool(row.get("tmeet_enabled"))
    resolved.tmeet_bin = row.get("tmeet_bin") or cfg.tmeet_bin
    resolved.tmeet_home = row.get("tmeet_home") or cfg.tmeet_home
    resolved.tmeet_timeout_seconds = float(row.get("tmeet_timeout_seconds") or cfg.tmeet_timeout_seconds)
    resolved.tmeet_allowed_commands = row.get("tmeet_allowed_commands") or cfg.tmeet_allowed_commands
    return resolved
