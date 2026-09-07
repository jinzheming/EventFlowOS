from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from personal_affairs.application.idempotency import json_safe


class LLMProfilesRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list_profiles(self, user_id: UUID, active_only: bool = False) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, name, provider_key, preset_key, base_url, model_name, auth_ref,
                   capabilities, default_params, privacy_tier, active, priority,
                   created_at, updated_at
            FROM personal_affairs.llm_profiles
            WHERE user_id = %s
              AND (%s = false OR active = true)
            ORDER BY active DESC, priority ASC, created_at DESC
            """,
            (user_id, active_only),
        ).fetchall()
        return list(rows)

    def create_profile(
        self,
        user_id: UUID,
        name: str,
        provider_key: str,
        preset_key: str | None,
        base_url: str | None,
        model_name: str,
        auth_ref: str | None,
        capabilities: dict[str, Any],
        default_params: dict[str, Any],
        privacy_tier: str,
        active: bool,
        priority: int,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.llm_profiles(
                user_id, name, provider_key, preset_key, base_url, model_name, auth_ref,
                capabilities, default_params, privacy_tier, active, priority
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, name, provider_key, preset_key, base_url, model_name, auth_ref,
                      capabilities, default_params, privacy_tier, active, priority,
                      created_at, updated_at
            """,
            (
                user_id,
                name,
                provider_key,
                preset_key,
                base_url,
                model_name,
                auth_ref,
                Jsonb(json_safe(capabilities)),
                Jsonb(json_safe(default_params)),
                privacy_tier,
                active,
                priority,
            ),
        ).fetchone()
        assert row is not None
        return row

    def patch_profile(self, user_id: UUID, profile_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {
            "name",
            "provider_key",
            "preset_key",
            "base_url",
            "model_name",
            "auth_ref",
            "capabilities",
            "default_params",
            "privacy_tier",
            "active",
            "priority",
        }
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key not in allowed:
                continue
            updates.append(f"{key} = %s")
            params.append(Jsonb(json_safe(value)) if key in {"capabilities", "default_params"} else value)
        if not updates:
            return self.get_profile(user_id, profile_id)
        updates.append("updated_at = now()")
        params.extend([profile_id, user_id])
        return self.conn.execute(
            f"""
            UPDATE personal_affairs.llm_profiles
            SET {', '.join(updates)}
            WHERE id = %s AND user_id = %s
            RETURNING id, name, provider_key, preset_key, base_url, model_name, auth_ref,
                      capabilities, default_params, privacy_tier, active, priority,
                      created_at, updated_at
            """,
            params,
        ).fetchone()

    def get_profile(self, user_id: UUID, profile_id: UUID) -> dict | None:
        return self.conn.execute(
            """
            SELECT id, name, provider_key, preset_key, base_url, model_name, auth_ref,
                   capabilities, default_params, privacy_tier, active, priority,
                   created_at, updated_at
            FROM personal_affairs.llm_profiles
            WHERE id = %s AND user_id = %s
            """,
            (profile_id, user_id),
        ).fetchone()

    def delete_profile(self, user_id: UUID, profile_id: UUID) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.llm_profiles WHERE id = %s AND user_id = %s RETURNING id",
            (profile_id, user_id),
        ).fetchone()
        return row is not None

    def list_bindings(
        self,
        user_id: UUID,
        purpose_key: str | None = None,
        active_only: bool = False,
    ) -> list[dict]:
        where = ["b.user_id = %s"]
        params: list[Any] = [user_id]
        if purpose_key is not None:
            where.append("b.purpose_key = %s")
            params.append(purpose_key)
        if active_only:
            where.append("b.active = true AND p.active = true")
        rows = self.conn.execute(
            f"""
            SELECT b.id, b.purpose_key, b.scope_type, b.scope_value, b.profile_id,
                   b.override_params, b.instructions, b.active, b.priority,
                   b.created_at, b.updated_at,
                   p.name AS profile_name, p.provider_key, p.model_name
            FROM personal_affairs.llm_bindings b
            JOIN personal_affairs.llm_profiles p ON p.id = b.profile_id
            WHERE {' AND '.join(where)}
            ORDER BY b.active DESC, b.priority ASC, b.created_at DESC
            """,
            params,
        ).fetchall()
        return list(rows)

    def create_binding(
        self,
        user_id: UUID,
        purpose_key: str,
        scope_type: str,
        scope_value: str | None,
        profile_id: UUID,
        override_params: dict[str, Any],
        instructions: str | None,
        active: bool,
        priority: int,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.llm_bindings(
                user_id, purpose_key, scope_type, scope_value, profile_id,
                override_params, instructions, active, priority
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                purpose_key,
                scope_type,
                scope_value,
                profile_id,
                Jsonb(json_safe(override_params)),
                instructions,
                active,
                priority,
            ),
        ).fetchone()
        assert row is not None
        created = self.get_binding(user_id, row["id"])
        assert created is not None
        return created

    def patch_binding(self, user_id: UUID, binding_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {
            "purpose_key",
            "scope_type",
            "scope_value",
            "profile_id",
            "override_params",
            "instructions",
            "active",
            "priority",
        }
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key not in allowed:
                continue
            updates.append(f"{key} = %s")
            params.append(Jsonb(json_safe(value)) if key == "override_params" else value)
        if not updates:
            return self.get_binding(user_id, binding_id)
        updates.append("updated_at = now()")
        params.extend([binding_id, user_id])
        row = self.conn.execute(
            f"""
            UPDATE personal_affairs.llm_bindings
            SET {', '.join(updates)}
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            params,
        ).fetchone()
        if not row:
            return None
        return self.get_binding(user_id, row["id"])

    def get_binding(self, user_id: UUID, binding_id: UUID) -> dict | None:
        return self.conn.execute(
            """
            SELECT b.id, b.purpose_key, b.scope_type, b.scope_value, b.profile_id,
                   b.override_params, b.instructions, b.active, b.priority,
                   b.created_at, b.updated_at,
                   p.name AS profile_name, p.provider_key, p.model_name
            FROM personal_affairs.llm_bindings b
            JOIN personal_affairs.llm_profiles p ON p.id = b.profile_id
            WHERE b.id = %s AND b.user_id = %s
            """,
            (binding_id, user_id),
        ).fetchone()

    def delete_binding(self, user_id: UUID, binding_id: UUID) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.llm_bindings WHERE id = %s AND user_id = %s RETURNING id",
            (binding_id, user_id),
        ).fetchone()
        return row is not None

    def resolve_binding(
        self,
        user_id: UUID,
        purpose_key: str,
        scope_type: str = "global",
        scope_value: str | None = None,
    ) -> dict | None:
        return self.conn.execute(
            """
            SELECT b.id AS binding_id, b.purpose_key, b.scope_type, b.scope_value,
                   b.override_params, b.instructions AS binding_instructions,
                   b.priority AS binding_priority,
                   p.id AS profile_id, p.name AS profile_name, p.provider_key,
                   p.preset_key, p.base_url, p.model_name, p.auth_ref,
                   p.capabilities, p.default_params, p.privacy_tier,
                   p.priority AS profile_priority
            FROM personal_affairs.llm_bindings b
            JOIN personal_affairs.llm_profiles p ON p.id = b.profile_id
            WHERE b.user_id = %s
              AND b.purpose_key = %s
              AND b.active = true
              AND p.active = true
              AND (
                b.scope_type = 'global'
                OR (b.scope_type = %s AND b.scope_value IS NOT DISTINCT FROM %s)
              )
            ORDER BY
              CASE
                WHEN b.scope_type = %s AND b.scope_value IS NOT DISTINCT FROM %s THEN 0
                WHEN b.scope_type = 'global' THEN 1
                ELSE 2
              END,
              b.priority ASC,
              p.priority ASC,
              b.created_at DESC
            LIMIT 1
            """,
            (user_id, purpose_key, scope_type, scope_value, scope_type, scope_value),
        ).fetchone()
