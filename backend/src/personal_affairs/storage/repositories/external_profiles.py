from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from personal_affairs.application.idempotency import json_safe


class ExternalProfilesRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list_profiles(
        self,
        user_id: UUID,
        capability: str | None = None,
        active_only: bool = False,
    ) -> list[dict]:
        where = ["user_id = %s"]
        params: list[Any] = [user_id]
        if capability is not None:
            where.append("capability = %s")
            params.append(capability)
        if active_only:
            where.append("active = true")
        rows = self.conn.execute(
            f"""
            SELECT id, name, provider_key, preset_key, capability, auth_ref,
                   active, priority, created_at, updated_at
            FROM personal_affairs.external_profiles
            WHERE {' AND '.join(where)}
            ORDER BY active DESC, priority ASC, created_at DESC
            """,
            params,
        ).fetchall()
        return list(rows)

    def create_profile(
        self,
        user_id: UUID,
        name: str,
        provider_key: str,
        preset_key: str | None,
        capability: str,
        auth_ref: str | None,
        active: bool,
        priority: int,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.external_profiles(
                user_id, name, provider_key, preset_key, capability, auth_ref, active, priority
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, name, provider_key, preset_key, capability, auth_ref,
                      active, priority, created_at, updated_at
            """,
            (user_id, name, provider_key, preset_key, capability, auth_ref, active, priority),
        ).fetchone()
        assert row is not None
        return row

    def patch_profile(self, user_id: UUID, profile_id: UUID, patch: dict[str, Any]) -> dict | None:
        allowed = {"name", "provider_key", "preset_key", "capability", "auth_ref", "active", "priority"}
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key not in allowed:
                continue
            updates.append(f"{key} = %s")
            params.append(value)
        if not updates:
            return self.get_profile(user_id, profile_id)
        updates.append("updated_at = now()")
        params.extend([profile_id, user_id])
        return self.conn.execute(
            f"""
            UPDATE personal_affairs.external_profiles
            SET {', '.join(updates)}
            WHERE id = %s AND user_id = %s
            RETURNING id, name, provider_key, preset_key, capability, auth_ref,
                      active, priority, created_at, updated_at
            """,
            params,
        ).fetchone()

    def get_profile(self, user_id: UUID, profile_id: UUID) -> dict | None:
        return self.conn.execute(
            """
            SELECT id, name, provider_key, preset_key, capability, auth_ref,
                   active, priority, created_at, updated_at
            FROM personal_affairs.external_profiles
            WHERE id = %s AND user_id = %s
            """,
            (profile_id, user_id),
        ).fetchone()

    def delete_profile(self, user_id: UUID, profile_id: UUID) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.external_profiles WHERE id = %s AND user_id = %s RETURNING id",
            (profile_id, user_id),
        ).fetchone()
        return row is not None

    def list_bindings(
        self,
        user_id: UUID,
        purpose_key: str | None = None,
        capability: str | None = None,
        active_only: bool = False,
    ) -> list[dict]:
        where = ["b.user_id = %s"]
        params: list[Any] = [user_id]
        if purpose_key is not None:
            where.append("b.purpose_key = %s")
            params.append(purpose_key)
        if capability is not None:
            where.append("p.capability = %s")
            params.append(capability)
        if active_only:
            where.append("b.active = true AND p.active = true")
        rows = self.conn.execute(
            f"""
            SELECT b.id, b.profile_id, b.purpose_key, b.scope_type, b.scope_value,
                   b.target_ref, b.format_key, b.field_mapping, b.value_mapping,
                   b.instructions, b.conflict_policy, b.dry_run, b.active,
                   b.priority, b.last_used_at, b.last_error, b.created_at, b.updated_at,
                   p.name AS profile_name, p.provider_key, p.preset_key, p.capability,
                   p.auth_ref
            FROM personal_affairs.external_bindings b
            JOIN personal_affairs.external_profiles p ON p.id = b.profile_id
            WHERE {' AND '.join(where)}
            ORDER BY b.active DESC, b.priority ASC, p.priority ASC, b.created_at DESC
            """,
            params,
        ).fetchall()
        return list(rows)

    def create_binding(
        self,
        user_id: UUID,
        profile_id: UUID,
        purpose_key: str,
        scope_type: str,
        scope_value: str | None,
        target_ref: str,
        format_key: str,
        field_mapping: dict[str, Any],
        value_mapping: dict[str, Any],
        instructions: str | None,
        conflict_policy: str,
        dry_run: bool,
        active: bool,
        priority: int,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO personal_affairs.external_bindings(
                user_id, profile_id, purpose_key, scope_type, scope_value, target_ref,
                format_key, field_mapping, value_mapping, instructions, conflict_policy,
                dry_run, active, priority
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                profile_id,
                purpose_key,
                scope_type,
                scope_value,
                target_ref,
                format_key,
                Jsonb(json_safe(field_mapping)),
                Jsonb(json_safe(value_mapping)),
                instructions,
                conflict_policy,
                dry_run,
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
            "profile_id",
            "purpose_key",
            "scope_type",
            "scope_value",
            "target_ref",
            "format_key",
            "field_mapping",
            "value_mapping",
            "instructions",
            "conflict_policy",
            "dry_run",
            "active",
            "priority",
            "last_error",
        }
        updates: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key not in allowed:
                continue
            updates.append(f"{key} = %s")
            params.append(Jsonb(json_safe(value)) if key in {"field_mapping", "value_mapping"} else value)
        if not updates:
            return self.get_binding(user_id, binding_id)
        updates.append("updated_at = now()")
        params.extend([binding_id, user_id])
        row = self.conn.execute(
            f"""
            UPDATE personal_affairs.external_bindings
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
            SELECT b.id, b.profile_id, b.purpose_key, b.scope_type, b.scope_value,
                   b.target_ref, b.format_key, b.field_mapping, b.value_mapping,
                   b.instructions, b.conflict_policy, b.dry_run, b.active,
                   b.priority, b.last_used_at, b.last_error, b.created_at, b.updated_at,
                   p.name AS profile_name, p.provider_key, p.preset_key, p.capability,
                   p.auth_ref
            FROM personal_affairs.external_bindings b
            JOIN personal_affairs.external_profiles p ON p.id = b.profile_id
            WHERE b.id = %s AND b.user_id = %s
            """,
            (binding_id, user_id),
        ).fetchone()

    def delete_binding(self, user_id: UUID, binding_id: UUID) -> bool:
        row = self.conn.execute(
            "DELETE FROM personal_affairs.external_bindings WHERE id = %s AND user_id = %s RETURNING id",
            (binding_id, user_id),
        ).fetchone()
        return row is not None

    def resolve_bindings(
        self,
        user_id: UUID,
        purpose_key: str,
        capability: str | None = None,
        scope_type: str = "global",
        scope_value: str | None = None,
    ) -> list[dict]:
        where = ["b.user_id = %s", "b.purpose_key = %s"]
        params: list[Any] = [user_id, purpose_key]
        if capability is not None:
            where.append("p.capability = %s")
            params.append(capability)
        where.extend(
            [
                "b.active = true",
                "p.active = true",
                """
                (
                  b.scope_type = 'global'
                  OR (b.scope_type = %s AND b.scope_value IS NOT DISTINCT FROM %s)
                )
                """,
            ]
        )
        params.extend([scope_type, scope_value, scope_type, scope_value])
        rows = self.conn.execute(
            f"""
            SELECT b.id, b.profile_id, b.purpose_key, b.scope_type, b.scope_value,
                   b.target_ref, b.format_key, b.field_mapping, b.value_mapping,
                   b.instructions, b.conflict_policy, b.dry_run, b.active,
                   b.priority, b.last_used_at, b.last_error, b.created_at, b.updated_at,
                   p.name AS profile_name, p.provider_key, p.preset_key, p.capability,
                   p.auth_ref, p.priority AS profile_priority
            FROM personal_affairs.external_bindings b
            JOIN personal_affairs.external_profiles p ON p.id = b.profile_id
            WHERE {' AND '.join(where)}
            ORDER BY
              CASE
                WHEN b.scope_type = %s AND b.scope_value IS NOT DISTINCT FROM %s THEN 0
                WHEN b.scope_type = 'global' THEN 1
                ELSE 2
              END,
              b.priority ASC,
              p.priority ASC,
              b.created_at DESC
            """,
            params,
        ).fetchall()
        return list(rows)
