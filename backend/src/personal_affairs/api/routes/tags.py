from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import ItemOut, TagCreate, TagOut, TagPatch
from personal_affairs.application.tag_service import TagService
from personal_affairs.domain.enums import ItemScope
from personal_affairs.storage.repositories.tags import TagsRepository

router = APIRouter(prefix="/tags", tags=["tags"])


def _build_tree(rows: list[dict]) -> list[dict]:
    """Two-level tree: parents first (created_at order), children nested."""
    by_id: dict[UUID, dict] = {row["id"]: dict(row) for row in rows}
    for row in by_id.values():
        row["children"] = []
    roots: list[dict] = []
    for row in by_id.values():
        if row["parent_id"] and row["parent_id"] in by_id:
            by_id[row["parent_id"]]["children"].append(row)
        else:
            roots.append(row)
    return roots


@router.get("", response_model=list[TagOut])
def list_tags(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return _build_tree(TagsRepository(conn).list_tags(user_id))


@router.post("", response_model=TagOut, dependencies=[Depends(require_csrf)])
def create_tag(
    request: TagCreate,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    tag = TagService(TagsRepository(conn)).create(user_id, request.name, request.color, request.parent_id)
    response.status_code = 201
    return tag


@router.patch("/{tag_id}", response_model=TagOut, dependencies=[Depends(require_csrf)])
def patch_tag(
    tag_id: UUID,
    request: TagPatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    tag = TagService(TagsRepository(conn)).patch(user_id, tag_id, request.model_dump(exclude_unset=True))
    if not tag:
        return not_found()
    return tag


@router.delete("/{tag_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_tag(
    tag_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not TagsRepository(conn).delete(user_id, tag_id):
        return not_found()
    return Response(status_code=204)


@router.get("/{tag_id}/items", response_model=list[ItemOut])
def tag_items(
    tag_id: UUID,
    include_done: bool = False,
    scope: ItemScope | None = None,
    recursive: bool = True,
    limit: int = Query(200, ge=1, le=500),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    repo = TagsRepository(conn)
    if not repo.get(user_id, tag_id):
        return not_found()
    return repo.items_for_tag(user_id, tag_id, include_done, scope, recursive, limit)
