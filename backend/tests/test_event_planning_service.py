from datetime import UTC, datetime
from typing import Any, cast

from psycopg import Connection

from personal_affairs.application import event_planning_service as planning
from personal_affairs.application.location_service import AMapClient, RouteEstimate


class FakeAMap:
    enabled = True

    def __init__(self, durations: dict[str, int] | None = None):
        self.durations = durations or {}

    def route(self, origin, destination, mode):
        duration = self.durations.get(mode)
        if duration is None:
            return None
        return RouteEstimate(1000, duration, mode, "2026-11-03T00:00:00+00:00")

    def search_poi(self, query, *, limit=5):
        return {"status": "ok", "candidates": []}

    def resolve(self, query, *, limit=5):
        return {"status": "ok", "candidates": []}


def test_assess_candidate_checks_both_modes_and_applies_travel_factor():
    events = [
        {
            "id": "previous",
            "title": "前一场线下会议",
            "start": datetime(2026, 11, 3, 9, 0, tzinfo=UTC),
            "end": datetime(2026, 11, 3, 9, 30, tzinfo=UTC),
            "all_day": False,
            "event_format": "offline",
            "location_latitude": 31.2,
            "location_longitude": 121.4,
        }
    ]
    candidate = {
        "title": "客户拜访",
        "start_at": "2026-11-03T10:30:00+00:00",
        "due_at": "2026-11-03T11:00:00+00:00",
        "event_format": "offline",
        "location_latitude": 31.3,
        "location_longitude": 121.5,
    }

    result = planning.assess_candidate(
        events,
        candidate,
        cast(AMapClient, FakeAMap({"transit": 2400, "driving": 900})),
        "UTC",
    )

    assert result["status"] == "travel_warning"
    assert result["travel_factor"] == 1.5
    assert result["travel_modes"]["transit"]["status"] == "tight"
    assert result["travel_modes"]["driving"]["status"] == "ok"
    assert result["recommended_travel_mode"] == "driving"
    assert result["travel_checks"][0]["modes"]["driving"]["buffered_minutes"] == 23


def test_assess_candidate_detects_all_day_overlap():
    result = planning.assess_candidate(
        [
            {
                "id": "holiday",
                "title": "全天安排",
                "start": "2026-11-03",
                "end": "2026-11-03",
                "all_day": True,
            }
        ],
        {
            "title": "会议",
            "start_at": "2026-11-03T10:00:00+00:00",
            "due_at": "2026-11-03T11:00:00+00:00",
        },
        cast(AMapClient, FakeAMap()),
        "UTC",
    )

    assert result["status"] == "conflict"
    assert result["overlaps"][0]["id"] == "holiday"


def test_prepare_event_flags_ambiguous_venue(monkeypatch):
    class AmbiguousAMap(FakeAMap):
        def search_poi(self, query, *, limit=5):
            return {
                "status": "ok",
                "candidates": [
                    {"name": "会议中心北馆", "address": "北路 1 号"},
                    {"name": "会议中心南馆", "address": "南路 1 号"},
                ],
            }

    monkeypatch.setattr(planning, "_events_around_candidate", lambda *args: [])

    result = planning.prepare_event(
        cast(Any, object()),
        object(),
        {
            "title": "项目会",
            "start_at": "2026-11-03T10:00:00+00:00",
            "due_at": "2026-11-03T11:00:00+00:00",
            "event_format": "offline",
            "location_name": "会议中心",
        },
        cast(AMapClient, AmbiguousAMap()),
        "UTC",
    )

    assert result["assessment"]["status"] == "location_ambiguous"
    assert len(result["location_resolution"]["candidates"]) == 2


def test_assess_all_day_candidate_detects_timed_overlap():
    result = planning.assess_candidate(
        [
            {
                "id": "meeting",
                "title": "Existing meeting",
                "start": datetime(2026, 11, 3, 10, 0, tzinfo=UTC),
                "end": datetime(2026, 11, 3, 11, 0, tzinfo=UTC),
                "all_day": False,
            }
        ],
        {
            "title": "All-day event",
            "all_day": True,
            "start_date": "2026-11-03",
            "due_date": "2026-11-03",
        },
        cast(AMapClient, FakeAMap()),
        "UTC",
    )

    assert result["status"] == "conflict"
    assert result["overlaps"][0]["id"] == "meeting"


def test_online_events_do_not_trigger_physical_travel_checks():
    result = planning.assess_candidate(
        [
            {
                "id": "online",
                "title": "线上会议",
                "start": datetime(2026, 11, 3, 9, 0, tzinfo=UTC),
                "end": datetime(2026, 11, 3, 9, 30, tzinfo=UTC),
                "all_day": False,
                "event_format": "online",
            }
        ],
        {
            "title": "线下拜访",
            "start_at": "2026-11-03T10:00:00+00:00",
            "due_at": "2026-11-03T11:00:00+00:00",
            "event_format": "offline",
            "location_latitude": 31.3,
            "location_longitude": 121.5,
        },
        cast(AMapClient, FakeAMap()),
        "UTC",
    )

    assert result["status"] == "ready"
    assert result["travel_checks"] == []


def test_tight_and_impossible_modes_still_raise_a_travel_warning():
    previous = {
        "id": "previous",
        "title": "Previous meeting",
        "start": datetime(2026, 11, 3, 9, 0, tzinfo=UTC),
        "end": datetime(2026, 11, 3, 9, 30, tzinfo=UTC),
        "all_day": False,
        "event_format": "offline",
        "location_latitude": 31.2,
        "location_longitude": 121.4,
    }
    candidate = {
        "title": "Next meeting",
        "start_at": "2026-11-03T10:30:00+00:00",
        "due_at": "2026-11-03T11:00:00+00:00",
        "event_format": "offline",
        "location_latitude": 31.3,
        "location_longitude": 121.5,
    }

    result = planning.assess_candidate(
        [previous],
        candidate,
        cast(AMapClient, FakeAMap({"transit": 2700, "driving": 2400})),
        "UTC",
    )

    assert result["status"] == "travel_warning"
    assert result["travel_modes"]["transit"]["status"] == "impossible"
    assert result["travel_modes"]["driving"]["status"] == "tight"


def test_all_day_events_block_free_slots(monkeypatch):
    monkeypatch.setattr(
        planning,
        "_calendar_events",
        lambda *args: [
            {
                "id": "holiday",
                "title": "全天安排",
                "start": "2026-11-03",
                "end": "2026-11-03",
                "all_day": True,
            }
        ],
    )

    result = planning.find_meeting_slots(
        cast(Any, object()),
        object(),
        cast(AMapClient, FakeAMap()),
        "UTC",
        duration_minutes=30,
        start_date="2026-11-03",
        end_date="2026-11-03",
        event_format="online",
        preferred_start="09:00",
        preferred_end="10:00",
    )

    assert result["slots"] == []


def test_find_meeting_slots_applies_requested_buffer(monkeypatch):
    monkeypatch.setattr(
        planning,
        "_calendar_events",
        lambda *args: [
            {
                "id": "busy",
                "title": "已有事项",
                "start": datetime(2026, 11, 3, 10, 0, tzinfo=UTC),
                "end": datetime(2026, 11, 3, 11, 0, tzinfo=UTC),
                "all_day": False,
            }
        ],
    )

    result = planning.find_meeting_slots(
        cast(Any, object()),
        object(),
        cast(AMapClient, FakeAMap()),
        "UTC",
        duration_minutes=30,
        start_date="2026-11-03",
        end_date="2026-11-03",
        event_format="online",
        preferred_start="09:00",
        preferred_end="10:00",
        buffer_minutes=30,
    )

    assert [slot["start"] for slot in result["slots"]] == [
        "2026-11-03T09:00:00+00:00"
    ]


def test_schedule_summary_includes_daily_workload_and_conflicts(monkeypatch):
    events = [
        {
            "id": "holiday",
            "title": "全天安排",
            "start": "2026-11-03",
            "end": "2026-11-03",
            "all_day": True,
        },
        {
            "id": "meeting-a",
            "title": "会议 A",
            "start": datetime(2026, 11, 3, 10, 0, tzinfo=UTC),
            "end": datetime(2026, 11, 3, 11, 0, tzinfo=UTC),
            "all_day": False,
            "event_format": "online",
        },
        {
            "id": "meeting-b",
            "title": "会议 B",
            "start": datetime(2026, 11, 3, 10, 30, tzinfo=UTC),
            "end": datetime(2026, 11, 3, 11, 30, tzinfo=UTC),
            "all_day": False,
            "event_format": "offline",
        },
    ]
    monkeypatch.setattr(planning, "_calendar_events", lambda *args: events)

    result = planning.get_schedule_summary(
        cast(Connection, object()),
        object(),
        "UTC",
        "2026-11-03",
        "2026-11-03",
    )

    assert result["total_events"] == 3
    assert result["online_events"] == 1
    assert result["offline_events"] == 1
    assert result["all_day_events"] == 1
    assert result["scheduled_minutes"] == 120
    assert result["by_day"]["2026-11-03"] == {"events": 3, "minutes": 120}
    assert result["conflict_count"] >= 1


def test_calendar_query_excludes_items_touching_only_window_boundaries(monkeypatch):
    class FakeCalendarQuery:
        def events(self, *args):
            return [
                {
                    "id": "ends-at-start",
                    "all_day": False,
                    "start": datetime(2026, 11, 2, 23, 30, tzinfo=UTC),
                    "end": datetime(2026, 11, 3, 0, 0, tzinfo=UTC),
                },
                {
                    "id": "inside",
                    "all_day": False,
                    "start": datetime(2026, 11, 3, 10, 0, tzinfo=UTC),
                    "end": datetime(2026, 11, 3, 11, 0, tzinfo=UTC),
                },
                {
                    "id": "starts-at-end",
                    "all_day": False,
                    "start": datetime(2026, 11, 4, 0, 0, tzinfo=UTC),
                    "end": datetime(2026, 11, 4, 0, 30, tzinfo=UTC),
                },
            ]

    monkeypatch.setattr(planning, "CalendarQueryService", lambda *args: FakeCalendarQuery())

    events = planning._calendar_events(
        cast(Any, object()),
        object(),
        "2026-11-03T00:00:00+00:00",
        "2026-11-04T00:00:00+00:00",
        "UTC",
    )

    assert [event["id"] for event in events] == ["inside"]
