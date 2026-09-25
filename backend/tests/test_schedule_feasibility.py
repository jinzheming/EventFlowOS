from datetime import datetime, timedelta
from uuid import uuid4

from personal_affairs.application.location_service import RouteEstimate
from personal_affairs.application.schedule_feasibility import assess_schedule_feasibility


class FakeItems:
    def __init__(self, rows: list[dict]):
        self.rows = {row["id"]: row for row in rows}

    def get_item(self, _user_id, item_id):
        return self.rows.get(item_id)


class FakeMap:
    def __init__(self, route: RouteEstimate | None):
        self.route_value = route

    def route(self, *_args, **_kwargs):
        return self.route_value


def _pair(gap_minutes: int, *, with_locations: bool = True) -> tuple[list[dict], object, object]:
    user_id = uuid4()
    first_id, second_id = uuid4(), uuid4()
    start = datetime(2026, 9, 22, 9, 0)
    first = {
        "id": first_id, "title": "出发", "start_at": start, "due_at": start + timedelta(minutes=30),
        "event_format": "offline", "location_latitude": 31.2 if with_locations else None,
        "location_longitude": 121.5 if with_locations else None,
    }
    second = {
        "id": second_id, "title": "到达", "start_at": start + timedelta(minutes=30 + gap_minutes),
        "due_at": start + timedelta(minutes=60 + gap_minutes), "event_format": "offline",
        "location_latitude": 31.21 if with_locations else None, "location_longitude": 121.51 if with_locations else None,
    }
    return [first, second], user_id, [first_id, second_id]


def test_schedule_is_feasible_when_gap_covers_route_and_buffer() -> None:
    rows, user_id, ids = _pair(30)
    result = assess_schedule_feasibility(
        FakeItems(rows), user_id, ids, FakeMap(RouteEstimate(1000, 600, "transit", "2026-09-22T01:00:00+00:00")),
        travel_mode="transit", buffer_minutes=15,
    )
    assert result["feasible"] is True
    assert result["checks"][0]["travel_seconds"] == 600


def test_schedule_warns_when_gap_is_too_short() -> None:
    rows, user_id, ids = _pair(10)
    result = assess_schedule_feasibility(
        FakeItems(rows), user_id, ids, FakeMap(RouteEstimate(1000, 1800, "transit", "2026-09-22T01:00:00+00:00")),
        travel_mode="transit", buffer_minutes=15,
    )
    assert result["feasible"] is False
    assert result["checks"][0]["warning_level"] == "critical"
    assert result["checks"][0]["shortfall_seconds"] > 0


def test_schedule_marks_unresolved_physical_location_unknown() -> None:
    rows, user_id, ids = _pair(60, with_locations=False)
    result = assess_schedule_feasibility(FakeItems(rows), user_id, ids, FakeMap(None))
    assert result["feasible"] is False
    assert result["checks"][0]["reason"] == "location_unknown"
