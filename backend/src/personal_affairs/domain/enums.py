from enum import StrEnum


class ItemScope(StrEnum):
    WORK = "work"
    PERSONAL = "personal"


class ItemStatus(StrEnum):
    INBOX = "inbox"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ProjectStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectHealth(StrEnum):
    UNKNOWN = "unknown"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BLOCKED = "blocked"


class ProgressMode(StrEnum):
    MANUAL = "manual"
    MILESTONE = "milestone"


class MilestoneStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"


class ReminderTiming(StrEnum):
    AT_START = "at_start"
    BEFORE_START = "before_start"
    BEFORE_DUE = "before_due"


class DeliveryChannel(StrEnum):
    IN_APP = "in_app"
    FEISHU = "feishu"
    NTFY = "ntfy"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    RETRY_WAIT = "retry_wait"
    DEAD = "dead"
    CANCELLED = "cancelled"
