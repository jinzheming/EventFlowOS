from datetime import date

from personal_affairs.application.agent_context_service import (
    build_executive_briefing,
    build_free_slots,
    calendar_conflicts,
)


def test_executive_briefing_orders_items_and_conflicts() -> None:
    items = [
        {
            "id": "later",
            "title": "下午事项",
            "status": "planned",
            "priority": "normal",
            "start_at": "2026-08-24T15:00:00+08:00",
        },
        {
            "id": "overdue",
            "title": "昨天遗留",
            "status": "planned",
            "priority": "high",
            "due_date": "2026-08-23",
        },
        {
            "id": "done",
            "title": "已完成",
            "status": "done",
            "priority": "urgent",
            "start_at": "2026-08-24T09:00:00+08:00",
        },
    ]
    events = [
        {"id": "a", "title": "A", "kind": "work_item", "source_id": "a", "start": "2026-08-24T10:00:00+08:00", "end": "2026-08-24T11:00:00+08:00", "all_day": False},
        {"id": "b", "title": "B", "kind": "work_item", "source_id": "b", "start": "2026-08-24T10:30:00+08:00", "end": "2026-08-24T11:30:00+08:00", "all_day": False},
    ]

    briefing = build_executive_briefing(
        items=items,
        proposals=[{"id": "p2", "created_at": "2026-08-24T09:00:00+08:00"}, {"id": "p1", "created_at": "2026-08-24T08:00:00+08:00"}],
        reminders=[{"id": "r1"}],
        calendar_events=events,
        active_focus={"id": "f1"},
        day=date(2026, 8, 24),
        timezone="Asia/Shanghai",
        window_days=1,
    )

    assert [item["id"] for item in briefing["today_items"]] == ["later"]
    assert [item["id"] for item in briefing["overdue_items"]] == ["overdue"]
    assert [proposal["id"] for proposal in briefing["pending_proposals"]] == ["p2", "p1"]
    assert briefing["summary"] == {
        "today_item_count": 1,
        "overdue_item_count": 1,
        "pending_proposal_count": 2,
        "unread_reminder_count": 1,
        "calendar_conflict_count": 1,
        "focus_active": True,
    }


def test_calendar_conflicts_are_stable() -> None:
    conflicts = calendar_conflicts(
        [
            {"id": "b", "title": "B", "kind": "work_item", "source_id": "b", "start": "2026-08-24T10:30:00+08:00", "end": "2026-08-24T11:30:00+08:00", "all_day": False},
            {"id": "a", "title": "A", "kind": "work_item", "source_id": "a", "start": "2026-08-24T10:00:00+08:00", "end": "2026-08-24T11:00:00+08:00", "all_day": False},
        ],
        "Asia/Shanghai",
    )

    assert len(conflicts) == 1
    assert conflicts[0]["start"].isoformat() == "2026-08-24T10:30:00+08:00"
    assert [event["id"] for event in conflicts[0]["events"]] == ["a", "b"]


def test_build_free_slots_skips_busy_intervals_without_mutating_input() -> None:
    events = [
        {"id": "busy", "title": "Busy", "kind": "work_item", "source_id": "busy", "start": "2026-08-24T10:00:00+08:00", "end": "2026-08-24T11:00:00+08:00", "all_day": False},
    ]
    original = [event.copy() for event in events]

    slots = build_free_slots(
        calendar_events=events,
        start_day=date(2026, 8, 24),
        end_day=date(2026, 8, 24),
        timezone="Asia/Shanghai",
        duration_minutes=60,
        preferred_start="09:00",
        preferred_end="12:00",
        buffer_minutes=0,
        limit=3,
    )

    assert [(slot["start"].isoformat(), slot["end"].isoformat()) for slot in slots] == [
        ("2026-08-24T09:00:00+08:00", "2026-08-24T10:00:00+08:00"),
        ("2026-08-24T11:00:00+08:00", "2026-08-24T12:00:00+08:00"),
    ]
    assert events == original
