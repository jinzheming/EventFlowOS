from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from personal_affairs.domain.enums import ItemScope, ItemStatus, MilestoneStatus, ProgressMode
from personal_affairs.domain.errors import ErrorCode, validation_error
from personal_affairs.domain.models import ItemSchedule, MilestoneSnapshot

LEGAL_TRANSITIONS: dict[ItemStatus, set[ItemStatus]] = {
    ItemStatus.INBOX: {
        ItemStatus.INBOX,
        ItemStatus.PLANNED,
        ItemStatus.IN_PROGRESS,
        ItemStatus.WAITING,
        ItemStatus.DONE,
        ItemStatus.CANCELLED,
    },
    ItemStatus.PLANNED: {
        ItemStatus.PLANNED,
        ItemStatus.IN_PROGRESS,
        ItemStatus.WAITING,
        ItemStatus.DONE,
        ItemStatus.CANCELLED,
    },
    ItemStatus.IN_PROGRESS: {
        ItemStatus.IN_PROGRESS,
        ItemStatus.PLANNED,
        ItemStatus.WAITING,
        ItemStatus.DONE,
        ItemStatus.CANCELLED,
    },
    ItemStatus.WAITING: {
        ItemStatus.WAITING,
        ItemStatus.PLANNED,
        ItemStatus.IN_PROGRESS,
        ItemStatus.DONE,
        ItemStatus.CANCELLED,
    },
    ItemStatus.DONE: {ItemStatus.DONE, ItemStatus.PLANNED},
    ItemStatus.CANCELLED: {ItemStatus.CANCELLED, ItemStatus.PLANNED},
}


def validate_item_transition(before: ItemStatus, after: ItemStatus) -> None:
    if after not in LEGAL_TRANSITIONS[before]:
        raise validation_error(
            ErrorCode.INVALID_STATUS_TRANSITION,
            f"Item status cannot move from {before} to {after}.",
        )


def validate_project_link(scope: ItemScope, project_id: object | None) -> None:
    if scope == ItemScope.PERSONAL and project_id is not None:
        raise validation_error(
            ErrorCode.PERSONAL_ITEM_PROJECT_FORBIDDEN,
            "Personal items cannot link to projects.",
        )


def validate_schedule(schedule: ItemSchedule) -> None:
    if schedule.all_day:
        if schedule.start_at or schedule.due_at:
            raise validation_error(ErrorCode.INVALID_SCHEDULE, "All-day items use date fields only.")
        if schedule.start_date and schedule.due_date and schedule.start_date > schedule.due_date:
            raise validation_error(ErrorCode.INVALID_SCHEDULE, "Start date must not be after due date.")
    else:
        if schedule.start_date or schedule.due_date:
            raise validation_error(ErrorCode.INVALID_SCHEDULE, "Timed items use datetime fields only.")
        if schedule.start_at and schedule.due_at and schedule.start_at > schedule.due_at:
            raise validation_error(ErrorCode.INVALID_SCHEDULE, "Start time must not be after due time.")


def all_day_notification_time(day: date, timezone: str) -> datetime:
    local = datetime(day.year, day.month, day.day, 9, 0, tzinfo=ZoneInfo(timezone))
    return local.astimezone(ZoneInfo("UTC"))


def validate_tag_parent(
    tag_id: UUID | None,
    parent_id: UUID,
    parent_row: dict[str, Any] | None,
    current: dict[str, Any] | None,
    has_children: bool,
) -> None:
    """Enforce the two-level tag hierarchy.

    - A tag cannot be its own parent.
    - The parent must exist and be a top-level tag (parent_id IS NULL).
    - A top-level tag that already has children cannot be demoted to a child
      (its children would become grandchildren, i.e. depth three).
    """
    if tag_id is not None and tag_id == parent_id:
        raise validation_error(ErrorCode.TAG_INVALID_PARENT, "标签不能作为自身的父标签")
    if parent_row is None:
        raise validation_error(ErrorCode.TAG_INVALID_PARENT, "父标签不存在")
    if parent_row.get("parent_id") is not None:
        raise validation_error(ErrorCode.TAG_DEPTH_EXCEEDED, "仅支持两层标签：子标签的父级必须是顶层标签")
    if current is not None and current.get("parent_id") is None and has_children:
        raise validation_error(ErrorCode.TAG_DEPTH_EXCEEDED, "带有子标签的标签不能移动到子层")


def add_recurrence_delta(day: date, freq: str, interval: int) -> date:
    if freq == "daily":
        return day + timedelta(days=interval)
    if freq == "weekly":
        return day + timedelta(weeks=interval)
    # monthly: clamp to the last day of shorter months (Jan 31 + 1 month → Feb 28/29)
    month_index = day.month - 1 + interval
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def next_occurrence_schedule(item: dict[str, Any]) -> dict[str, Any] | None:
    """Compute schedule fields for the next occurrence of a completed recurring
    item, or None when the rule ends (no anchor, until passed, count exhausted).

    Timed occurrences shift by whole days, so the local wall-clock time is
    preserved (DST-agnostic for Asia/Shanghai)."""
    freq = item.get("recurrence_freq")
    if not freq:
        return None
    count = item.get("recurrence_count")
    if count is not None and count <= 1:
        return None
    interval = item.get("recurrence_interval") or 1
    until = item.get("recurrence_until")
    if item.get("all_day", True):
        anchor: date | None = item.get("due_date") or item.get("start_date")
        if anchor is None:
            return None
        delta = add_recurrence_delta(anchor, freq, interval) - anchor
        start = item["start_date"] + delta if item.get("start_date") else None
        due = item["due_date"] + delta if item.get("due_date") else None
        next_day = due or start
        if until and next_day and next_day > until:
            return None
        return {"all_day": True, "start_at": None, "due_at": None, "start_date": start, "due_date": due}
    anchor_at: datetime | None = item.get("due_at") or item.get("start_at")
    if anchor_at is None:
        return None
    delta = add_recurrence_delta(anchor_at.date(), freq, interval) - anchor_at.date()
    start_at = item["start_at"] + delta if item.get("start_at") else None
    due_at = item["due_at"] + delta if item.get("due_at") else None
    next_at = due_at or start_at
    if until and next_at and next_at.date() > until:
        return None
    return {"all_day": False, "start_date": None, "due_date": None, "start_at": start_at, "due_at": due_at}


def calculate_project_progress(
    mode: ProgressMode,
    milestones: list[MilestoneSnapshot],
    manual_percent: int | None,
) -> int | None:
    if mode == ProgressMode.MANUAL:
        if manual_percent is None:
            return None
        return max(0, min(100, manual_percent))
    active = [m for m in milestones if m.status != MilestoneStatus.CANCELLED]
    if not active:
        return None
    total = sum(max(0, m.weight) for m in active)
    if total <= 0:
        return None
    done = sum(max(0, m.weight) for m in active if m.status == MilestoneStatus.DONE)
    return round(done * 100 / total)
