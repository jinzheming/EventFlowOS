from typing import Any
from uuid import UUID

from personal_affairs.api.schemas import ItemCreate, ItemPatch
from personal_affairs.application.idempotency import create_request_hash
from personal_affairs.application.item_intake_normalizer import ItemIntakeNormalizer
from personal_affairs.domain.enums import ItemScope, ItemStatus
from personal_affairs.domain.errors import ErrorCode, conflict_error
from personal_affairs.domain.models import ItemSchedule
from personal_affairs.domain.policies import (
    next_occurrence_schedule,
    validate_item_transition,
    validate_project_link,
    validate_schedule,
)
from personal_affairs.storage.repositories.activity import ActivityRepository
from personal_affairs.storage.repositories.event_outbox import EventOutboxRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.people import PeopleRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository
from personal_affairs.storage.repositories.tags import TagsRepository

TERMINAL_STATUSES = {ItemStatus.DONE.value, ItemStatus.CANCELLED.value, "done", "cancelled"}
INTAKE_META_KEYS = {"intake_text", "intake_scope_source", "intake_origin", "intake_normalization"}


def _schedule_from_payload(payload: dict) -> ItemSchedule:
    return ItemSchedule(
        all_day=payload.get("all_day", True),
        start_at=payload.get("start_at"),
        due_at=payload.get("due_at"),
        start_date=payload.get("start_date"),
        due_date=payload.get("due_date"),
    )


def _people_payload(raw: list[Any] | None) -> list[dict[str, Any]] | None:
    if raw is None:
        return None
    people: list[dict[str, Any]] = []
    seen: set[str] = set()
    for person in raw:
        data = person if isinstance(person, dict) else person.model_dump()
        person_id = data["person_id"]
        key = str(person_id)
        if key in seen:
            continue
        seen.add(key)
        people.append({"person_id": person_id, "role": data["role"]})
    return people


def _has_waiting_person(people: list[dict[str, Any]] | None) -> bool:
    return any(person.get("role") == "waiting" for person in people or [])


def _apply_people_status(payload: dict[str, Any], people: list[dict[str, Any]] | None, current_status: str | None = None) -> None:
    if people is None:
        return
    requested_status = payload.get("status")
    if requested_status in TERMINAL_STATUSES or current_status in TERMINAL_STATUSES:
        return
    if _has_waiting_person(people):
        payload["status"] = ItemStatus.WAITING.value
    elif (requested_status == ItemStatus.WAITING.value) or (requested_status is None and current_status == ItemStatus.WAITING.value):
        payload["status"] = ItemStatus.PLANNED.value


def _should_normalize_intake(payload: dict[str, Any]) -> bool:
    return payload.get("intake_normalization") == "llm"


class ItemService:
    def __init__(self, items: ItemsRepository, activity: ActivityRepository, normalizer: ItemIntakeNormalizer | None = None):
        self.items = items
        self.activity = activity
        self.normalizer = normalizer

    def create(
        self,
        user_id: UUID,
        request: ItemCreate,
        *,
        created_by_actor: str = "human",
        source_context: dict[str, Any] | None = None,
        execution_output: dict[str, Any] | None = None,
    ) -> tuple[dict, bool]:
        raw_payload = request.model_dump(exclude_none=True)
        client_request_id = raw_payload.pop("client_request_id", None)
        request_hash = create_request_hash(raw_payload)  # 包含 tag_ids、people 和 intake metadata
        if client_request_id:
            state, snapshot = self.items.replay_create_request(
                user_id, "item", client_request_id, request_hash
            )
            if state == "conflict":
                raise conflict_error(
                    ErrorCode.IDEMPOTENCY_CONFLICT,
                    "client_request_id was already used with a different payload.",
                )
            if state == "replay" and snapshot:
                return snapshot, False
        payload = dict(raw_payload)
        normalization: dict[str, Any] | None = None
        if self.normalizer and _should_normalize_intake(payload):
            payload, normalization = self.normalizer.normalize(user_id, self.items.conn, payload)
        for key in INTAKE_META_KEYS:
            payload.pop(key, None)
        tag_ids = payload.pop("tag_ids", None)
        people = _people_payload(payload.pop("people", None))
        _apply_people_status(payload, people)
        validate_project_link(ItemScope(payload["scope"]), payload.get("project_id"))
        validate_schedule(_schedule_from_payload(payload))
        payload["created_by_actor"] = created_by_actor
        payload["updated_by_actor"] = created_by_actor
        if source_context is not None:
            payload["source_context"] = source_context
        if execution_output is not None:
            payload["execution_output"] = execution_output
        if normalization:
            payload["source_context"] = {**(payload.get("source_context") or {}), "intake_normalization": normalization}
        item = self.items.create_item(user_id, payload)
        if people is not None:
            PeopleRepository(self.items.conn).replace_item_people(user_id, item["id"], people)
            item = self.items.get_item(user_id, item["id"]) or item
        if tag_ids is not None:
            TagsRepository(self.items.conn).replace_item_tags(user_id, item["id"], tag_ids)
            item = self.items.get_item(user_id, item["id"]) or item
        if client_request_id:
            self.items.record_create_request(user_id, client_request_id, request_hash, "item", item["id"], item)
        activity_payload: dict[str, Any] = {"scope": payload["scope"]}
        if normalization:
            activity_payload["intake_normalization"] = normalization
        self.activity.record(user_id, "item", item["id"], "created", activity_payload)
        EventOutboxRepository(self.items.conn).record(
            user_id, "item.created", "item", item["id"], {"scope": payload["scope"]}
        )
        return item, True

    def patch(
        self,
        user_id: UUID,
        item_id: UUID,
        current: dict,
        expected_version: int,
        request: ItemPatch,
        *,
        updated_by_actor: str = "human",
        source_context: dict[str, Any] | None = None,
        execution_output: dict[str, Any] | None = None,
    ) -> dict:
        patch = request.model_dump(exclude_unset=True)
        tag_ids = patch.pop("tag_ids", None)
        people = _people_payload(patch.pop("people", None))
        _apply_people_status(patch, people, current.get("status"))
        next_payload = {**current, **patch}
        validate_project_link(ItemScope(next_payload["scope"]), next_payload.get("project_id"))
        validate_schedule(_schedule_from_payload(next_payload))
        if "status" in patch:
            validate_item_transition(ItemStatus(current["status"]), ItemStatus(patch["status"]))
        activity_fields = sorted(patch.keys())
        patch["updated_by_actor"] = updated_by_actor
        if source_context is not None:
            patch["source_context"] = source_context
        if execution_output is not None:
            patch["execution_output"] = execution_output
        updated = self.items.patch_item(user_id, item_id, expected_version, patch)
        if not updated:
            raise conflict_error(ErrorCode.VERSION_CONFLICT, "Item version is stale.")
        if people is not None:
            PeopleRepository(self.items.conn).replace_item_people(user_id, item_id, people)
            updated = self.items.get_item(user_id, item_id) or updated
        if tag_ids is not None:
            TagsRepository(self.items.conn).replace_item_tags(user_id, item_id, tag_ids)
            updated = self.items.get_item(user_id, item_id) or updated
        if updated["status"] in {"done", "cancelled"}:
            self.items.cancel_pending_deliveries(user_id, item_id)
        fields = activity_fields
        if people is not None:
            fields.append("people")
        if tag_ids is not None:
            fields.append("tag_ids")
        self.activity.record(user_id, "item", item_id, "updated", {"fields": fields})
        if patch.get("status") == "done":
            EventOutboxRepository(self.items.conn).record(
                user_id, "item.completed", "item", item_id, {"scope": updated["scope"]}
            )
            self._materialize_next_occurrence(user_id, updated)
        return updated

    def _materialize_next_occurrence(self, user_id: UUID, item: dict) -> None:
        schedule = next_occurrence_schedule(item)
        if schedule is None:
            return
        count = item.get("recurrence_count")
        payload = {
            "scope": item["scope"],
            "project_id": item.get("project_id"),
            "title": item["title"],
            "notes": item.get("notes"),
            "status": "planned",
            "priority": item["priority"],
            "recurrence_freq": item["recurrence_freq"],
            "recurrence_interval": item.get("recurrence_interval") or 1,
            "recurrence_until": item.get("recurrence_until"),
            "recurrence_count": count - 1 if count is not None else None,
            **schedule,
        }
        validate_schedule(_schedule_from_payload(payload))
        created = self.items.create_item(user_id, payload)
        # 标签跟随到下一次发生
        tags = item.get("tags") or []
        if tags:
            TagsRepository(self.items.conn).replace_item_tags(
                user_id, created["id"], [tag["id"] for tag in tags]
            )
        people = item.get("people") or []
        if people:
            PeopleRepository(self.items.conn).replace_item_people(
                user_id, created["id"], [{"person_id": person["id"], "role": person["role"]} for person in people]
            )
        # The active reminder rides along so the worker follows the new occurrence.
        reminder = RemindersRepository(self.items.conn).get_active_for_item(user_id, item["id"])
        if reminder:
            RemindersRepository(self.items.conn).upsert_for_item(user_id, created["id"], reminder)
        self.activity.record(user_id, "item", created["id"], "created", {"scope": payload["scope"], "recurrence": True})
