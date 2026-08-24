from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import (
    current_user_id,
    db_conn,
    if_match_version,
    require_csrf,
)
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import (
    ItemOut,
    MilestoneCreate,
    MilestoneOut,
    MilestonePatch,
    ProjectCreate,
    ProjectOut,
    ProjectPatch,
    ProjectUpdateCreate,
    ProjectUpdateOut,
)
from personal_affairs.application.project_service import ProjectService
from personal_affairs.storage.repositories.activity import ActivityRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.projects import ProjectsRepository

router = APIRouter(prefix="/projects", tags=["projects"])


def _etag(response: Response, row: dict) -> None:
    response.headers["etag"] = f'"v{row["version"]}"'


@router.get("", response_model=list[ProjectOut])
def list_projects(
    include_archived: bool = False,
    limit: int = Query(100, ge=1, le=500),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ProjectsRepository(conn).list_projects(user_id, include_archived, limit)


@router.post("", response_model=ProjectOut, dependencies=[Depends(require_csrf)])
def create_project(
    request: ProjectCreate,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    service = ProjectService(ProjectsRepository(conn), ItemsRepository(conn), ActivityRepository(conn))
    project, created = service.create(user_id, request)
    response.status_code = 201 if created else 200
    _etag(response, project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: UUID,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    project = ProjectsRepository(conn).get_project(user_id, project_id)
    if not project:
        return not_found()
    _etag(response, project)
    return project


@router.patch("/{project_id}", response_model=ProjectOut, dependencies=[Depends(require_csrf)])
def patch_project(
    project_id: UUID,
    request: ProjectPatch,
    response: Response,
    expected_version: int = Depends(if_match_version),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    project = ProjectService(ProjectsRepository(conn), ItemsRepository(conn), ActivityRepository(conn)).patch(
        user_id, project_id, expected_version, request
    )
    _etag(response, project)
    return project


@router.post("/{project_id}/archive", response_model=ProjectOut, dependencies=[Depends(require_csrf)])
def archive_project(
    project_id: UUID,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    project = ProjectsRepository(conn).set_archive(user_id, project_id, True)
    if not project:
        return not_found()
    _etag(response, project)
    return project


@router.post("/{project_id}/restore", response_model=ProjectOut, dependencies=[Depends(require_csrf)])
def restore_project(
    project_id: UUID,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    project = ProjectsRepository(conn).set_archive(user_id, project_id, False)
    if not project:
        return not_found()
    _etag(response, project)
    return project


@router.get("/{project_id}/items", response_model=list[ItemOut])
def list_project_items(
    project_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ItemsRepository(conn).list_items(user_id, None, False, project_id, None, 200)


@router.get("/{project_id}/milestones", response_model=list[MilestoneOut])
def list_milestones(
    project_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ProjectsRepository(conn).list_milestones(user_id, project_id)


@router.post("/{project_id}/milestones", response_model=MilestoneOut, dependencies=[Depends(require_csrf)])
def create_milestone(
    project_id: UUID,
    request: MilestoneCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    if not ProjectsRepository(conn).get_project(user_id, project_id):
        return not_found()
    return ProjectsRepository(conn).create_milestone(user_id, project_id, request.model_dump())


@router.patch(
    "/{project_id}/milestones/{milestone_id}",
    response_model=MilestoneOut,
    dependencies=[Depends(require_csrf)],
)
def patch_milestone(
    project_id: UUID,
    milestone_id: UUID,
    request: MilestonePatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    row = ProjectsRepository(conn).update_milestone(user_id, milestone_id, request.model_dump(exclude_unset=True))
    if not row or row["project_id"] != project_id:
        return not_found()
    return row


@router.delete("/{project_id}/milestones/{milestone_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_milestone(
    project_id: UUID,
    milestone_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> None:
    repo = ProjectsRepository(conn)
    existing = repo.conn.execute(
        "SELECT project_id FROM personal_affairs.milestones WHERE user_id = %s AND id = %s",
        (user_id, milestone_id),
    ).fetchone()
    if not existing or existing["project_id"] != project_id:
        return not_found()
    repo.delete_milestone(user_id, milestone_id)


@router.get("/{project_id}/updates", response_model=list[ProjectUpdateOut])
def list_updates(
    project_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ProjectsRepository(conn).list_updates(user_id, project_id)


@router.post("/{project_id}/updates", response_model=ProjectUpdateOut, dependencies=[Depends(require_csrf)])
def create_update(
    project_id: UUID,
    request: ProjectUpdateCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    if not ProjectsRepository(conn).get_project(user_id, project_id):
        return not_found()
    return ProjectsRepository(conn).create_update(user_id, project_id, request.model_dump(exclude_none=True))
