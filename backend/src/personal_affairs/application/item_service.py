from typing import Any
from uuid import UUID

from personal_affairs.api.schemas import ItemCreate, ItemPatch
from personal_affairs.application.idempotency import create_request_hash
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


def _normalize_event_fields(payload: dict[str, Any]) -> None:
    """Keep the single activity form contract consistent before persistence."""
    event_format = payload.get("event_format")
    value = getattr(event_format, "value", event_format)
    if value == "online":
        payload["event_location"] = None
        for key in ("location_name", "location_address", "location_provider", "location_poi_id", "location_latitude", "location_longitude", "location_confidence", "location_updated_at"):
            payload[key] = None
    elif value == "offline":
        payload["event_url"] = None


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


class ItemService:
    def __init__(self, items: ItemsRepository, activity: ActivityRepository):
        self.items = items
        self.activity = activity

    def create(
        self,
        user_id: UUID,
        request: ItemCreate,
        *,
        created_by_actor: str = "human",
        source_context: dict[str, Any] | None = None,
        execution_output: dict[str, Any] | None = None,
    ) -> tuple[dict, bool]:
        payload = request.model_dump(exclude_none=True)
        client_request_id = payload.pop("client_request_id", None)
        request_hash = create_request_hash(payload)  # 包含 tag_ids 和 people
        tag_ids = payload.pop("tag_ids", None)
        people = _people_payload(payload.pop("people", None))
        predecessor_item_ids = payload.pop("predecessor_item_ids", None)
        successor_item_ids = payload.pop("successor_item_ids", None)
        _apply_people_status(payload, people)
        _normalize_event_fields(payload)
        validate_project_link(ItemScope(payload["scope"]), payload.get("project_id"))
        validate_schedule(_schedule_from_payload(payload))
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
        payload["created_by_actor"] = created_by_actor
        payload["updated_by_actor"] = created_by_actor
        if source_context is not None:
            payload["source_context"] = source_context
        if execution_output is not None:
            payload["execution_output"] = execution_output
        item = self.items.create_item(user_id, payload)
        if people is not None:
            PeopleRepository(self.items.conn).replace_item_people(user_id, item["id"], people)
            item = self.items.get_item(user_id, item["id"]) or item
        if tag_ids is not None:
            TagsRepository(self.items.conn).replace_item_tags(user_id, item["id"], tag_ids)
            item = self.items.get_item(user_id, item["id"]) or item
        if predecessor_item_ids is not None or successor_item_ids is not None:
            self.items.replace_item_relations(
                user_id, item["id"], predecessor_item_ids or [], successor_item_ids or []
            )
            item = self.items.get_item(user_id, item["id"]) or item
        if client_request_id:
            self.items.record_create_request(user_id, client_request_id, request_hash, "item", item["id"], item)
        self.activity.record(user_id, "item", item["id"], "created", {"scope": payload["scope"]})
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
        predecessor_item_ids = patch.pop("predecessor_item_ids", None)
        successor_item_ids = patch.pop("successor_item_ids", None)
        _apply_people_status(patch, people, current.get("status"))
        next_payload = {**current, **patch}
        _normalize_event_fields(next_payload)
        for key in ("event_format", "event_location", "event_url", "location_name", "location_address", "location_provider", "location_poi_id", "location_latitude", "location_longitude", "location_confidence", "location_updated_at"):
            if key in next_payload and key not in patch and next_payload[key] != current.get(key):
                patch[key] = next_payload[key]
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
        if predecessor_item_ids is not None or successor_item_ids is not None:
            existing_predecessors = current.get("predecessor_item_ids", [])
            existing_successors = current.get("successor_item_ids", [])
            self.items.replace_item_relations(
                user_id,
                item_id,
                existing_predecessors if predecessor_item_ids is None else predecessor_item_ids,
                existing_successors if successor_item_ids is None else successor_item_ids,
            )
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
            "event_format": item.get("event_format"),
            "event_location": item.get("event_location"),
            "event_url": item.get("event_url"),
            "location_name": item.get("location_name"),
            "location_address": item.get("location_address"),
            "location_provider": item.get("location_provider"),
            "location_poi_id": item.get("location_poi_id"),
            "location_latitude": item.get("location_latitude"),
            "location_longitude": item.get("location_longitude"),
            "location_confidence": item.get("location_confidence"),
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
