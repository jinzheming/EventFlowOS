from uuid import UUID

from personal_affairs.api.schemas import ProjectCreate, ProjectPatch
from personal_affairs.application.idempotency import create_request_hash
from personal_affairs.domain.errors import ErrorCode, conflict_error
from personal_affairs.storage.repositories.activity import ActivityRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.projects import ProjectsRepository


class ProjectService:
    def __init__(self, projects: ProjectsRepository, items: ItemsRepository, activity: ActivityRepository):
        self.projects = projects
        self.items = items
        self.activity = activity

    def create(self, user_id: UUID, request: ProjectCreate) -> tuple[dict, bool]:
        payload = request.model_dump(exclude_none=True)
        client_request_id = payload.pop("client_request_id", None)
        request_hash = create_request_hash(payload)
        if client_request_id:
            state, snapshot = self.items.replay_create_request(
                user_id, "project", client_request_id, request_hash
            )
            if state == "conflict":
                raise conflict_error(
                    ErrorCode.IDEMPOTENCY_CONFLICT,
                    "client_request_id was already used with a different payload.",
                )
            if state == "replay" and snapshot:
                return snapshot, False
        project = self.projects.create_project(user_id, payload)
        if client_request_id:
            self.items.record_create_request(
                user_id, client_request_id, request_hash, "project", project["id"], project
            )
        self.activity.record(user_id, "project", project["id"], "created", {})
        return project, True

    def patch(self, user_id: UUID, project_id: UUID, expected_version: int, request: ProjectPatch) -> dict:
        patch = request.model_dump(exclude_unset=True)
        updated = self.projects.patch_project(user_id, project_id, expected_version, patch)
        if not updated:
            raise conflict_error(ErrorCode.VERSION_CONFLICT, "Project version is stale.")
        self.activity.record(user_id, "project", project_id, "updated", {"fields": sorted(patch.keys())})
        return updated
