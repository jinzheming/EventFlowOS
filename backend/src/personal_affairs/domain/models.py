from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from personal_affairs.domain.enums import (
    ItemScope,
    ItemStatus,
    MilestoneStatus,
    Priority,
    ProjectHealth,
    ProjectStatus,
)


@dataclass(frozen=True)
class ItemSchedule:
    all_day: bool = True
    start_at: datetime | None = None
    due_at: datetime | None = None
    start_date: date | None = None
    due_date: date | None = None


@dataclass(frozen=True)
class ItemSnapshot:
    id: UUID | None
    user_id: UUID
    scope: ItemScope
    title: str
    status: ItemStatus = ItemStatus.INBOX
    priority: Priority = Priority.NORMAL
    project_id: UUID | None = None
    schedule: ItemSchedule = field(default_factory=ItemSchedule)


@dataclass(frozen=True)
class MilestoneSnapshot:
    id: UUID | None
    title: str
    status: MilestoneStatus
    weight: int


@dataclass(frozen=True)
class ProjectSnapshot:
    id: UUID | None
    user_id: UUID
    name: str
    status: ProjectStatus = ProjectStatus.PLANNED
    health: ProjectHealth = ProjectHealth.UNKNOWN
    progress_percent: int | None = None
