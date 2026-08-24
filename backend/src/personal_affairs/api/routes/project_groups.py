from uuid import UUID

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import ProjectGroupCreate, ProjectGroupOut, ProjectGroupPatch
from personal_affairs.storage.repositories.project_groups import ProjectGroupsRepository

router = APIRouter(prefix="/project-groups", tags=["project-groups"])


@router.get("", response_model=list[ProjectGroupOut])
def list_project_groups(
    include_archived: bool = Query(False),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ProjectGroupsRepository(conn).list_groups(user_id, include_archived)


@router.post("", response_model=ProjectGroupOut, status_code=201, dependencies=[Depends(require_csrf)])
def create_project_group(
    request: ProjectGroupCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return ProjectGroupsRepository(conn).create(user_id, request.name, request.color, request.sort_order)


@router.patch("/{group_id}", response_model=ProjectGroupOut, dependencies=[Depends(require_csrf)])
def patch_project_group(
    group_id: UUID,
    request: ProjectGroupPatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    group = ProjectGroupsRepository(conn).update(user_id, group_id, request.model_dump(exclude_unset=True))
    if not group:
        return not_found()
    return group


@router.post("/{group_id}/archive", response_model=ProjectGroupOut, dependencies=[Depends(require_csrf)])
def archive_project_group(
    group_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    group = ProjectGroupsRepository(conn).set_archive(user_id, group_id, True)
    if not group:
        return not_found()
    return group


@router.post("/{group_id}/restore", response_model=ProjectGroupOut, dependencies=[Depends(require_csrf)])
def restore_project_group(
    group_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    group = ProjectGroupsRepository(conn).set_archive(user_id, group_id, False)
    if not group:
        return not_found()
    return group
