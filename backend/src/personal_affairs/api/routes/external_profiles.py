from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import (
    ExternalBindingCreate,
    ExternalBindingOut,
    ExternalBindingPatch,
    ExternalProfileCreate,
    ExternalProfileOut,
    ExternalProfilePatch,
    ExternalProfilePresetOut,
    ExternalPurposePresetOut,
)
from personal_affairs.application.external_profiles import (
    external_profile_presets,
    external_purpose_presets,
    normalize_external_binding,
    normalize_external_profile,
)
from personal_affairs.domain.errors import validation_error
from personal_affairs.storage.repositories.external_profiles import ExternalProfilesRepository

router = APIRouter(tags=["external-profiles"])


def _clean_profile_payload(payload: dict) -> dict:
    cleaned = dict(payload)
    for key in ("name", "provider_key", "preset_key", "capability", "auth_ref"):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = str(cleaned[key]).strip()
            if key == "name" and not cleaned[key]:
                raise validation_error("EXTERNAL_PROFILE_INVALID", "name cannot be blank.")
            if key != "name" and not cleaned[key]:
                cleaned[key] = None
    return cleaned


def _clean_binding_payload(payload: dict) -> dict:
    cleaned = dict(payload)
    for key in ("purpose_key", "scope_type", "scope_value", "target_ref", "format_key", "instructions", "conflict_policy"):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = str(cleaned[key]).strip()
            if key in {"purpose_key", "target_ref", "format_key"} and not cleaned[key]:
                raise validation_error("EXTERNAL_BINDING_INVALID", f"{key} cannot be blank.")
            if key not in {"purpose_key", "target_ref", "format_key"} and not cleaned[key]:
                cleaned[key] = None
    return cleaned


@router.get("/external-profiles/presets", response_model=list[ExternalProfilePresetOut])
def list_external_profile_presets() -> list[dict]:
    return external_profile_presets()


@router.get("/external-profiles/purposes", response_model=list[ExternalPurposePresetOut])
def list_external_purpose_presets() -> list[dict]:
    return external_purpose_presets()


@router.get("/external-profiles", response_model=list[ExternalProfileOut])
def list_external_profiles(
    capability: str | None = None,
    active_only: bool = False,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ExternalProfilesRepository(conn).list_profiles(user_id, capability, active_only)


@router.post("/external-profiles", response_model=ExternalProfileOut, dependencies=[Depends(require_csrf)])
def create_external_profile(
    request: ExternalProfileCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    payload = _clean_profile_payload(request.model_dump())
    return ExternalProfilesRepository(conn).create_profile(
        user_id,
        payload["name"],
        payload["provider_key"],
        payload.get("preset_key"),
        payload["capability"],
        payload.get("auth_ref"),
        payload["active"],
        payload["priority"],
    )


@router.patch("/external-profiles/{profile_id}", response_model=ExternalProfileOut, dependencies=[Depends(require_csrf)])
def patch_external_profile(
    profile_id: UUID,
    request: ExternalProfilePatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    repo = ExternalProfilesRepository(conn)
    current = repo.get_profile(user_id, profile_id)
    if not current:
        return not_found()

    patch = _clean_profile_payload(request.model_dump(exclude_unset=True))
    if {"provider_key", "capability", "preset_key", "auth_ref"} & set(patch):
        try:
            normalized = normalize_external_profile(
                patch.get("provider_key", current["provider_key"]),
                patch.get("capability", current["capability"]),
                preset_key=patch.get("preset_key", current.get("preset_key")),
                auth_ref=patch.get("auth_ref", current.get("auth_ref")),
            )
        except ValueError as exc:
            raise validation_error("EXTERNAL_PROFILE_INVALID", str(exc)) from exc
        patch.update(normalized)

    row = repo.patch_profile(user_id, profile_id, patch)
    if not row:
        return not_found()
    return row


@router.delete("/external-profiles/{profile_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_external_profile(
    profile_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not ExternalProfilesRepository(conn).delete_profile(user_id, profile_id):
        return not_found()
    return Response(status_code=204)


@router.get("/external-bindings", response_model=list[ExternalBindingOut])
def list_external_bindings(
    purpose_key: str | None = None,
    capability: str | None = None,
    active_only: bool = False,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ExternalProfilesRepository(conn).list_bindings(user_id, purpose_key, capability, active_only)


@router.get("/external-bindings/resolve", response_model=list[ExternalBindingOut])
def resolve_external_bindings(
    purpose_key: str = Query(min_length=1, max_length=120),
    capability: str | None = None,
    scope_type: str = "global",
    scope_value: str | None = None,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ExternalProfilesRepository(conn).resolve_bindings(user_id, purpose_key, capability, scope_type, scope_value)


@router.post("/external-bindings", response_model=ExternalBindingOut, dependencies=[Depends(require_csrf)])
def create_external_binding(
    request: ExternalBindingCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    repo = ExternalProfilesRepository(conn)
    if not repo.get_profile(user_id, request.profile_id):
        return not_found()
    payload = _clean_binding_payload(request.model_dump())
    return repo.create_binding(
        user_id,
        payload["profile_id"],
        payload["purpose_key"],
        payload["scope_type"],
        payload.get("scope_value"),
        payload["target_ref"],
        payload["format_key"],
        payload["field_mapping"],
        payload["value_mapping"],
        payload.get("instructions"),
        payload["conflict_policy"],
        payload["dry_run"],
        payload["active"],
        payload["priority"],
    )


@router.patch("/external-bindings/{binding_id}", response_model=ExternalBindingOut, dependencies=[Depends(require_csrf)])
def patch_external_binding(
    binding_id: UUID,
    request: ExternalBindingPatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    repo = ExternalProfilesRepository(conn)
    current = repo.get_binding(user_id, binding_id)
    if not current:
        return not_found()

    patch = _clean_binding_payload(request.model_dump(exclude_unset=True))
    if "profile_id" in patch and not repo.get_profile(user_id, patch["profile_id"]):
        return not_found()
    if {
        "purpose_key",
        "scope_type",
        "scope_value",
        "target_ref",
        "format_key",
        "field_mapping",
        "value_mapping",
        "instructions",
        "conflict_policy",
    } & set(patch):
        try:
            normalized = normalize_external_binding(
                patch.get("purpose_key", current["purpose_key"]),
                patch.get("scope_type", current["scope_type"]),
                patch.get("target_ref", current["target_ref"]),
                patch.get("format_key", current["format_key"]),
                scope_value=patch.get("scope_value", current.get("scope_value")),
                field_mapping=patch.get("field_mapping", current.get("field_mapping")),
                value_mapping=patch.get("value_mapping", current.get("value_mapping")),
                instructions=patch.get("instructions", current.get("instructions")),
                conflict_policy=patch.get("conflict_policy", current["conflict_policy"]),
            )
        except ValueError as exc:
            raise validation_error("EXTERNAL_BINDING_INVALID", str(exc)) from exc
        patch.update(normalized)

    row = repo.patch_binding(user_id, binding_id, patch)
    if not row:
        return not_found()
    return row


@router.delete("/external-bindings/{binding_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_external_binding(
    binding_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not ExternalProfilesRepository(conn).delete_binding(user_id, binding_id):
        return not_found()
    return Response(status_code=204)
