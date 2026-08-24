from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from random import Random

from personal_affairs.domain.enums import DeliveryStatus, ReminderTiming
from personal_affairs.domain.errors import ErrorCode, validation_error
from personal_affairs.domain.models import ItemSchedule
from personal_affairs.domain.policies import all_day_notification_time

BACKOFF_SECONDS = [30, 120, 600, 1800, 7200]


@dataclass(frozen=True)
class NotificationClassification:
    retryable: bool
    status: DeliveryStatus
    code: str


def calculate_reminder_schedule(
    schedule: ItemSchedule,
    timing: ReminderTiming,
    offset_minutes: int,
    timezone: str,
) -> datetime:
    target: datetime | None = None
    if schedule.all_day:
        target_day: date | None = schedule.start_date or schedule.due_date
        if target_day is not None:
            target = all_day_notification_time(target_day, timezone)
    elif timing in {ReminderTiming.AT_START, ReminderTiming.BEFORE_START}:
        target = schedule.start_at
    elif timing == ReminderTiming.BEFORE_DUE:
        target = schedule.due_at

    if target is None:
        raise validation_error(ErrorCode.REMINDER_TARGET_MISSING, "Reminder target time is missing.")
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    if timing in {ReminderTiming.BEFORE_START, ReminderTiming.BEFORE_DUE}:
        target = target - timedelta(minutes=offset_minutes)
    return target.astimezone(UTC)


def next_retry_at(attempt_count: int, now: datetime, jitter_seed: int) -> datetime | None:
    if attempt_count >= 6:
        return None
    index = max(0, min(attempt_count - 1, len(BACKOFF_SECONDS) - 1))
    base = BACKOFF_SECONDS[index]
    jitter = Random(jitter_seed).randint(0, max(1, base // 5))
    return now + timedelta(seconds=base + jitter)


def classify_notification_error(result_or_exception: object) -> NotificationClassification:
    status_code = getattr(result_or_exception, "status_code", None)
    if status_code is None:
        return NotificationClassification(True, DeliveryStatus.RETRY_WAIT, "NETWORK_ERROR")
    if 200 <= int(status_code) < 300:
        return NotificationClassification(False, DeliveryStatus.DELIVERED, "OK")
    if int(status_code) in {408, 429} or int(status_code) >= 500:
        return NotificationClassification(True, DeliveryStatus.RETRY_WAIT, f"HTTP_{status_code}")
    return NotificationClassification(False, DeliveryStatus.DEAD, f"HTTP_{status_code}")
