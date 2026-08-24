from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import (
    current_user_id,
    db_conn,
    if_match_version,
    require_csrf,
    settings,
)
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import ItemCreate, ItemOut, ItemPatch, ReminderOut, ReminderPut
from personal_affairs.application.item_service import ItemService
from personal_affairs.application.reminder_service import ReminderService
from personal_affairs.config import Settings
from personal_affairs.domain.enums import ItemScope, ItemStatus
from personal_affairs.storage.repositories.activity import ActivityRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository

router = APIRouter(prefix="/items", tags=["items"])


def _etag(response: Response, row: dict) -> None:
    response.headers["etag"] = f'"v{row["version"]}"'


@router.get("", response_model=list[ItemOut])
def list_items(
    scope: ItemScope | None = None,
    status: ItemStatus | None = None,
    project_id: UUID | None = None,
    include_archived: bool = False,
    deleted: bool = Query(False),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(100, ge=1, le=500),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return ItemsRepository(conn).list_items(user_id, scope, include_archived, project_id, status, limit, search, deleted)


@router.post("", response_model=ItemOut, dependencies=[Depends(require_csrf)])
def create_item(
    request: ItemCreate,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    service = ItemService(ItemsRepository(conn), ActivityRepository(conn))
    item, created = service.create(user_id, request)
    _etag(response, item)
    response.status_code = 201 if created else 200
    return item


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: UUID,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    item = ItemsRepository(conn).get_item(user_id, item_id)
    if not item:
        return not_found()
    _etag(response, item)
    return item


@router.patch("/{item_id}", response_model=ItemOut, dependencies=[Depends(require_csrf)])
def patch_item(
    item_id: UUID,
    request: ItemPatch,
    response: Response,
    expected_version: int = Depends(if_match_version),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    repo = ItemsRepository(conn)
    current = repo.get_item(user_id, item_id)
    if not current:
        return not_found()
    item = ItemService(repo, ActivityRepository(conn)).patch(user_id, item_id, current, expected_version, request)
    _etag(response, item)
    return item


@router.post("/{item_id}/complete", response_model=ItemOut, dependencies=[Depends(require_csrf)])
def complete_item(
    item_id: UUID,
    response: Response,
    expected_version: int = Depends(if_match_version),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return patch_item(item_id, ItemPatch(status=ItemStatus.DONE), response, expected_version, user_id, conn)


@router.post("/{item_id}/reopen", response_model=ItemOut, dependencies=[Depends(require_csrf)])
def reopen_item(
    item_id: UUID,
    response: Response,
    expected_version: int = Depends(if_match_version),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return patch_item(item_id, ItemPatch(status=ItemStatus.PLANNED), response, expected_version, user_id, conn)


@router.post("/{item_id}/cancel", response_model=ItemOut, dependencies=[Depends(require_csrf)])
def cancel_item(
    item_id: UUID,
    response: Response,
    expected_version: int = Depends(if_match_version),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return patch_item(item_id, ItemPatch(status=ItemStatus.CANCELLED), response, expected_version, user_id, conn)


@router.post("/{item_id}/archive", response_model=ItemOut, dependencies=[Depends(require_csrf)])
def archive_item(
    item_id: UUID,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    item = ItemsRepository(conn).set_archive(user_id, item_id, True)
    if not item:
        return not_found()
    _etag(response, item)
    return item


@router.post("/{item_id}/restore", response_model=ItemOut, dependencies=[Depends(require_csrf)])
def restore_item(
    item_id: UUID,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    item = ItemsRepository(conn).set_archive(user_id, item_id, False)
    if not item:
        return not_found()
    _etag(response, item)
    return item


@router.delete("/{item_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_item(
    item_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> None:
    if not ItemsRepository(conn).soft_delete(user_id, item_id):
        return not_found()
    RemindersRepository(conn).deactivate_for_item(user_id, item_id)


@router.post("/{item_id}/restore-deleted", response_model=ItemOut, dependencies=[Depends(require_csrf)])
def restore_deleted_item(
    item_id: UUID,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    item = ItemsRepository(conn).restore_deleted(user_id, item_id)
    if not item:
        return not_found()
    _etag(response, item)
    return item


@router.delete("/{item_id}/purge", status_code=204, dependencies=[Depends(require_csrf)])
def purge_item(
    item_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> None:
    if not ItemsRepository(conn).purge(user_id, item_id):
        return not_found()


@router.get("/{item_id}/reminder", response_model=ReminderOut)
def get_reminder(
    item_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    reminder = RemindersRepository(conn).get_active_for_item(user_id, item_id)
    if not reminder:
        return not_found()
    return reminder


@router.put("/{item_id}/reminder", response_model=ReminderOut, dependencies=[Depends(require_csrf)])
def put_reminder(
    item_id: UUID,
    request: ReminderPut,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
    cfg: Settings = Depends(settings),
) -> dict:
    if not ItemsRepository(conn).get_item(user_id, item_id):
        return not_found()
    return ReminderService(RemindersRepository(conn), ItemsRepository(conn), cfg).upsert(user_id, item_id, request)


@router.delete("/{item_id}/reminder", status_code=204, dependencies=[Depends(require_csrf)])
def delete_reminder(
    item_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> None:
    RemindersRepository(conn).deactivate_for_item(user_id, item_id)
