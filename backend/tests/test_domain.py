from datetime import UTC, date, datetime

import pytest

from personal_affairs.domain.enums import (
    DeliveryStatus,
    ItemScope,
    ItemStatus,
    MilestoneStatus,
    ProgressMode,
    ReminderTiming,
)
from personal_affairs.domain.errors import DomainError, ErrorCode
from personal_affairs.domain.models import ItemSchedule, MilestoneSnapshot
from personal_affairs.domain.policies import (
    add_recurrence_delta,
    calculate_project_progress,
    next_occurrence_schedule,
    validate_item_transition,
    validate_project_link,
    validate_schedule,
)
from personal_affairs.domain.reminder_state import (
    calculate_reminder_schedule,
    classify_notification_error,
    next_retry_at,
)


def test_personal_items_cannot_link_to_projects() -> None:
    with pytest.raises(DomainError) as raised:
        validate_project_link(ItemScope.PERSONAL, object())
    assert raised.value.code == ErrorCode.PERSONAL_ITEM_PROJECT_FORBIDDEN


def test_terminal_item_reopen_must_go_to_planned() -> None:
    validate_item_transition(ItemStatus.DONE, ItemStatus.PLANNED)
    with pytest.raises(DomainError):
        validate_item_transition(ItemStatus.DONE, ItemStatus.IN_PROGRESS)


def test_schedule_rejects_mixed_all_day_shape() -> None:
    with pytest.raises(DomainError):
        validate_schedule(
            ItemSchedule(all_day=True, start_at=datetime(2026, 1, 1, tzinfo=UTC), due_date=date(2026, 1, 2))
        )


def test_all_day_reminder_uses_local_0900_as_utc() -> None:
    scheduled = calculate_reminder_schedule(
        ItemSchedule(all_day=True, due_date=date(2026, 12, 31)),
        ReminderTiming.BEFORE_DUE,
        0,
        "Asia/Shanghai",
    )
    assert scheduled == datetime(2026, 12, 31, 1, 0, tzinfo=UTC)


def test_milestone_progress_ignores_cancelled() -> None:
    progress = calculate_project_progress(
        ProgressMode.MILESTONE,
        [
            MilestoneSnapshot(None, "a", MilestoneStatus.DONE, 2),
            MilestoneSnapshot(None, "b", MilestoneStatus.PENDING, 2),
            MilestoneSnapshot(None, "c", MilestoneStatus.CANCELLED, 100),
        ],
        None,
    )
    assert progress == 50


def test_retry_schedule_caps_after_six_attempts() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert next_retry_at(1, now, 42) is not None
    assert next_retry_at(6, now, 42) is None


def test_notification_error_classification() -> None:
    class Response:
        status_code = 503

    classified = classify_notification_error(Response())
    assert classified.retryable is True
    assert classified.status == DeliveryStatus.RETRY_WAIT


def test_recurrence_monthly_clamps_to_short_month() -> None:
    assert add_recurrence_delta(date(2026, 1, 31), "monthly", 1) == date(2026, 2, 28)
    assert add_recurrence_delta(date(2026, 8, 8), "daily", 3) == date(2026, 8, 11)
    assert add_recurrence_delta(date(2026, 8, 8), "weekly", 2) == date(2026, 8, 22)


def test_next_occurrence_all_day_shifts_span() -> None:
    item = {
        "all_day": True,
        "start_date": date(2026, 8, 8),
        "due_date": date(2026, 8, 10),
        "start_at": None,
        "due_at": None,
        "recurrence_freq": "weekly",
        "recurrence_interval": 1,
        "recurrence_until": None,
        "recurrence_count": None,
    }
    schedule = next_occurrence_schedule(item)
    assert schedule == {"all_day": True, "start_at": None, "due_at": None, "start_date": date(2026, 8, 15), "due_date": date(2026, 8, 17)}


def test_next_occurrence_timed_keeps_wall_clock() -> None:
    item = {
        "all_day": False,
        "start_date": None,
        "due_date": None,
        "start_at": None,
        "due_at": datetime(2026, 8, 8, 10, 0, tzinfo=UTC),
        "recurrence_freq": "daily",
        "recurrence_interval": 1,
        "recurrence_until": None,
        "recurrence_count": None,
    }
    schedule = next_occurrence_schedule(item)
    assert schedule and schedule["due_at"] == datetime(2026, 8, 9, 10, 0, tzinfo=UTC)


def test_next_occurrence_stops_at_until_and_count() -> None:
    base = {
        "all_day": True,
        "start_date": None,
        "due_date": date(2026, 8, 30),
        "start_at": None,
        "due_at": None,
        "recurrence_freq": "weekly",
        "recurrence_interval": 1,
        "recurrence_count": None,
        "recurrence_until": date(2026, 9, 1),
    }
    assert next_occurrence_schedule(base) is None
    assert next_occurrence_schedule({**base, "recurrence_until": None, "recurrence_count": 1}) is None
    assert next_occurrence_schedule({**base, "recurrence_until": None, "recurrence_count": 2}) is not None


def test_domain_error_survives_contextmanager_reraise() -> None:
    # Regression: a frozen dataclass DomainError turned into FrozenInstanceError
    # when Python re-set __traceback__ while the error propagated through a
    # generator-based context manager (e.g. the db_conn dependency), masking
    # intended 4xx responses with a 500.
    import contextlib

    @contextlib.contextmanager
    def passthrough():
        yield

    with pytest.raises(DomainError) as raised, passthrough():
        raise DomainError(ErrorCode.VERSION_CONFLICT, "If-Match header is required.", 412)
    assert raised.value.code == ErrorCode.VERSION_CONFLICT
    assert raised.value.http_status == 412
    assert raised.value.retryable is False
