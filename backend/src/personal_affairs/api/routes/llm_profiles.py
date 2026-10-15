from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import (
    LLMBindingCreate,
    LLMBindingOut,
    LLMBindingPatch,
    LLMProfileCreate,
    LLMProfileOut,
    LLMProfilePatch,
    LLMProfilePresetOut,
    LLMPurposePresetOut,
    LLMResolvedBindingOut,
)
from personal_affairs.application.llm_profiles import (
    llm_profile_presets,
    llm_purpose_presets,
    normalize_llm_binding,
    normalize_llm_profile,
)
from personal_affairs.domain.errors import validation_error
from personal_affairs.storage.repositories.llm_profiles import LLMProfilesRepository

router = APIRouter(tags=["llm-profiles"])


def _clean_profile_payload(payload: dict) -> dict:
    cleaned = dict(payload)
    for key in ("name", "base_url", "model_name", "auth_ref", "preset_key"):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = str(cleaned[key]).strip()
            if key in {"name", "model_name"} and not cleaned[key]:
                raise validation_error("LLM_PROFILE_INVALID", f"{key} cannot be blank.")
            if key not in {"name", "model_name"} and not cleaned[key]:
                cleaned[key] = None
    return cleaned


def _clean_binding_payload(payload: dict) -> dict:
    cleaned = dict(payload)
    for key in ("purpose_key", "scope_type", "scope_value", "instructions"):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = str(cleaned[key]).strip()
            if key == "purpose_key" and not cleaned[key]:
                raise validation_error("LLM_BINDING_INVALID", "purpose_key cannot be blank.")
            if key != "purpose_key" and not cleaned[key]:
                cleaned[key] = None
    return cleaned


@router.get("/llm-profiles/presets", response_model=list[LLMProfilePresetOut])
def list_llm_profile_presets() -> list[dict]:
    return llm_profile_presets()


@router.get("/llm-profiles/purposes", response_model=list[LLMPurposePresetOut])
def list_llm_purpose_presets() -> list[dict]:
    return llm_purpose_presets()


@router.get("/llm-profiles", response_model=list[LLMProfileOut])
def list_llm_profiles(
    active_only: bool = False,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return LLMProfilesRepository(conn).list_profiles(user_id, active_only)


@router.post("/llm-profiles", response_model=LLMProfileOut, dependencies=[Depends(require_csrf)])
def create_llm_profile(
    request: LLMProfileCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    payload = _clean_profile_payload(request.model_dump())
    return LLMProfilesRepository(conn).create_profile(
        user_id,
        payload["name"],
        payload["provider_key"],
        payload.get("preset_key"),
        payload.get("base_url"),
        payload["model_name"],
        payload.get("auth_ref"),
        payload["capabilities"],
        payload["default_params"],
        payload["privacy_tier"],
        payload["active"],
        payload["priority"],
    )


@router.patch("/llm-profiles/{profile_id}", response_model=LLMProfileOut, dependencies=[Depends(require_csrf)])
def patch_llm_profile(
    profile_id: UUID,
    request: LLMProfilePatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    repo = LLMProfilesRepository(conn)
    current = repo.get_profile(user_id, profile_id)
    if not current:
        return not_found()

    patch = _clean_profile_payload(request.model_dump(exclude_unset=True))
    if {"provider_key", "preset_key", "base_url", "model_name", "auth_ref", "capabilities", "default_params", "privacy_tier"} & set(patch):
        try:
            normalized = normalize_llm_profile(
                patch.get("provider_key", current["provider_key"]),
                patch.get("model_name", current["model_name"]),
                preset_key=patch.get("preset_key", current.get("preset_key")),
                base_url=patch.get("base_url", current.get("base_url")),
                auth_ref=patch.get("auth_ref", current.get("auth_ref")),
                capabilities=patch.get("capabilities", current.get("capabilities")),
                default_params=patch.get("default_params", current.get("default_params")),
                privacy_tier=patch.get("privacy_tier", current["privacy_tier"]),
            )
        except ValueError as exc:
            raise validation_error("LLM_PROFILE_INVALID", str(exc)) from exc
        patch.update(normalized)

    row = repo.patch_profile(user_id, profile_id, patch)
    if not row:
        return not_found()
    return row


@router.delete("/llm-profiles/{profile_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_llm_profile(
    profile_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not LLMProfilesRepository(conn).delete_profile(user_id, profile_id):
        return not_found()
    return Response(status_code=204)


@router.get("/llm-bindings", response_model=list[LLMBindingOut])
def list_llm_bindings(
    purpose_key: str | None = None,
    active_only: bool = False,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return LLMProfilesRepository(conn).list_bindings(user_id, purpose_key, active_only)


@router.get("/llm-bindings/resolve", response_model=LLMResolvedBindingOut | None)
def resolve_llm_binding(
    purpose_key: str = Query(min_length=1, max_length=120),
    scope_type: str = "global",
    scope_value: str | None = None,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict | None:
    try:
        normalized = normalize_llm_binding(purpose_key, scope_type, scope_value=scope_value)
    except ValueError as exc:
        raise validation_error("LLM_BINDING_INVALID", str(exc)) from exc
    return LLMProfilesRepository(conn).resolve_binding(
        user_id,
        normalized["purpose_key"],
        normalized["scope_type"],
        normalized["scope_value"],
    )


@router.post("/llm-bindings", response_model=LLMBindingOut, dependencies=[Depends(require_csrf)])
def create_llm_binding(
    request: LLMBindingCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    repo = LLMProfilesRepository(conn)
    if not repo.get_profile(user_id, request.profile_id):
        return not_found()
    payload = _clean_binding_payload(request.model_dump())
    return repo.create_binding(
        user_id,
        payload["purpose_key"],
        payload["scope_type"],
        payload.get("scope_value"),
        payload["profile_id"],
        payload["override_params"],
        payload.get("instructions"),
        payload["active"],
        payload["priority"],
    )


@router.patch("/llm-bindings/{binding_id}", response_model=LLMBindingOut, dependencies=[Depends(require_csrf)])
def patch_llm_binding(
    binding_id: UUID,
    request: LLMBindingPatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    repo = LLMProfilesRepository(conn)
    current = repo.get_binding(user_id, binding_id)
    if not current:
        return not_found()

    patch = _clean_binding_payload(request.model_dump(exclude_unset=True))
    if "profile_id" in patch and not repo.get_profile(user_id, patch["profile_id"]):
        return not_found()
    if {"purpose_key", "scope_type", "scope_value", "override_params", "instructions"} & set(patch):
        try:
            normalized = normalize_llm_binding(
                patch.get("purpose_key", current["purpose_key"]),
                patch.get("scope_type", current["scope_type"]),
                scope_value=patch.get("scope_value", current.get("scope_value")),
                override_params=patch.get("override_params", current.get("override_params")),
                instructions=patch.get("instructions", current.get("instructions")),
            )
        except ValueError as exc:
            raise validation_error("LLM_BINDING_INVALID", str(exc)) from exc
        patch.update(normalized)

    row = repo.patch_binding(user_id, binding_id, patch)
    if not row:
        return not_found()
    return row


@router.delete("/llm-bindings/{binding_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_llm_binding(
    binding_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not LLMProfilesRepository(conn).delete_binding(user_id, binding_id):
        return not_found()
    return Response(status_code=204)
