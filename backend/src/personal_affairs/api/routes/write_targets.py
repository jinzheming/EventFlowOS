from uuid import UUID

from fastapi import APIRouter, Depends, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import (
    WriteTargetCreate,
    WriteTargetOut,
    WriteTargetPatch,
    WriteTargetPresetOut,
)
from personal_affairs.application.write_targets import normalize_write_target, write_target_presets
from personal_affairs.domain.errors import validation_error
from personal_affairs.storage.repositories.write_targets import WriteTargetsRepository

router = APIRouter(prefix="/write-targets", tags=["write-targets"])


def _clean_payload(payload: dict) -> dict:
    cleaned = dict(payload)
    for key in ("name", "target_url"):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = str(cleaned[key]).strip()
            if not cleaned[key]:
                raise validation_error("WRITE_TARGET_INVALID", f"{key} cannot be blank.")
    if "instructions" in cleaned and cleaned["instructions"] is not None:
        cleaned["instructions"] = str(cleaned["instructions"]).strip() or None
    return cleaned


@router.get("/presets", response_model=list[WriteTargetPresetOut])
def list_write_target_presets() -> list[dict]:
    return write_target_presets()


@router.get("", response_model=list[WriteTargetOut])
def list_write_targets(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return WriteTargetsRepository(conn).list_for_user(user_id)


@router.post("", response_model=WriteTargetOut, dependencies=[Depends(require_csrf)])
def create_write_target(
    request: WriteTargetCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    payload = _clean_payload(request.model_dump())
    return WriteTargetsRepository(conn).create(
        user_id,
        payload["name"],
        payload["target_type"],
        payload["target_url"],
        payload["format_key"],
        payload["field_mapping"],
        payload.get("instructions"),
        payload["active"],
    )


@router.patch("/{target_id}", response_model=WriteTargetOut, dependencies=[Depends(require_csrf)])
def patch_write_target(
    target_id: UUID,
    request: WriteTargetPatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    repo = WriteTargetsRepository(conn)
    current = repo.get(user_id, target_id)
    if not current:
        return not_found()

    patch = _clean_payload(request.model_dump(exclude_unset=True))
    if {"target_type", "format_key", "field_mapping"} & set(patch):
        try:
            patch["format_key"], patch["field_mapping"] = normalize_write_target(
                patch.get("target_type", current["target_type"]),
                patch.get("format_key", current["format_key"]),
                patch.get("field_mapping", current["field_mapping"]),
            )
        except ValueError as exc:
            raise validation_error("WRITE_TARGET_INVALID", str(exc)) from exc

    row = repo.patch(user_id, target_id, patch)
    if not row:
        return not_found()
    return row


@router.delete("/{target_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_write_target(
    target_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not WriteTargetsRepository(conn).delete(user_id, target_id):
        return not_found()
    return Response(status_code=204)
