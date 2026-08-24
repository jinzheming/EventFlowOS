from uuid import UUID

from fastapi import APIRouter, Depends, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import SavedViewCreate, SavedViewOut, SavedViewPatch
from personal_affairs.storage.repositories.saved_views import SavedViewsRepository

router = APIRouter(prefix="/saved-views", tags=["saved-views"])


@router.get("", response_model=list[SavedViewOut])
def list_saved_views(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return SavedViewsRepository(conn).list(user_id)


@router.post("", response_model=SavedViewOut, status_code=201, dependencies=[Depends(require_csrf)])
def create_saved_view(
    request: SavedViewCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return SavedViewsRepository(conn).create(user_id, request.name, request.spec.model_dump(), request.sort_order)


@router.patch("/{view_id}", response_model=SavedViewOut, dependencies=[Depends(require_csrf)])
def patch_saved_view(
    view_id: UUID,
    request: SavedViewPatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    view = SavedViewsRepository(conn).update(user_id, view_id, request.model_dump(exclude_unset=True))
    if not view:
        return not_found()
    return view


@router.delete("/{view_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_saved_view(
    view_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not SavedViewsRepository(conn).delete(user_id, view_id):
        return not_found()
    return Response(status_code=204)
