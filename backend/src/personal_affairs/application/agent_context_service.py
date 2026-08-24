from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg import Connection

from personal_affairs.application.calendar_query_service import CalendarQueryService
from personal_affairs.config import Settings
from personal_affairs.storage.repositories.agent_proposals import AgentProposalsRepository
from personal_affairs.storage.repositories.focus import FocusRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.projects import ProjectsRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository

TERMINAL_STATUSES = {"done", "cancelled"}


def get_executive_briefing(
    conn: Connection,
    user_id: UUID,
    cfg: Settings,
    *,
    target_date: str | None = None,
    window_days: int = 1,
    include_done: bool = False,
) -> dict[str, Any]:
    tz = ZoneInfo(cfg.default_timezone)
    day = date.fromisoformat(target_date) if target_date else datetime.now(tz).date()
    window_days = max(1, min(window_days, 14))
    window_start = datetime.combine(day, time.min, tzinfo=tz)
    window_end = window_start + timedelta(days=window_days)

    items = ItemsRepository(conn).list_items(user_id, scope=None, include_archived=False, limit=500)
    proposals = AgentProposalsRepository(conn).list_pending(user_id, "pending", 50)
    reminders = RemindersRepository(conn).list_deliveries(
        user_id,
        limit=100,
        channel="in_app",
        status="delivered",
        unseen=True,
    )
    calendar_events = CalendarQueryService(ItemsRepository(conn), ProjectsRepository(conn)).events(
        user_id,
        window_start.isoformat(),
        window_end.isoformat(),
        {"work_item", "personal_item", "milestone"},
    )
    active_focus = FocusRepository(conn).active(user_id)

    briefing = build_executive_briefing(
        items=items,
        proposals=proposals,
        reminders=reminders,
        calendar_events=calendar_events,
        active_focus=active_focus,
        day=day,
        timezone=cfg.default_timezone,
        window_days=window_days,
        include_done=include_done,
    )
    return _json_safe(briefing)


def find_free_slots(
    conn: Connection,
    user_id: UUID,
    cfg: Settings,
    *,
    duration_minutes: int,
    start_date: str,
    end_date: str,
    preferred_start: str = "09:00",
    preferred_end: str = "18:00",
    buffer_minutes: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    tz = ZoneInfo(cfg.default_timezone)
    start_day = date.fromisoformat(start_date)
    end_day = date.fromisoformat(end_date)
    if end_day < start_day:
        start_day, end_day = end_day, start_day
    duration_minutes = max(1, min(duration_minutes, 24 * 60))
    buffer_minutes = max(0, min(buffer_minutes, 24 * 60))
    limit = max(1, min(limit, 100))
    window_start = datetime.combine(start_day, time.min, tzinfo=tz)
    window_end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz)
    events = CalendarQueryService(ItemsRepository(conn), ProjectsRepository(conn)).events(
        user_id,
        window_start.isoformat(),
        window_end.isoformat(),
        {"work_item", "personal_item"},
    )
    slots = build_free_slots(
        calendar_events=events,
        start_day=start_day,
        end_day=end_day,
        timezone=cfg.default_timezone,
        duration_minutes=duration_minutes,
        preferred_start=preferred_start,
        preferred_end=preferred_end,
        buffer_minutes=buffer_minutes,
        limit=limit,
    )
    return _json_safe(
        {
            "timezone": cfg.default_timezone,
            "window": {"start_date": start_day, "end_date": end_day},
            "duration_minutes": duration_minutes,
            "buffer_minutes": buffer_minutes,
            "busy_count": len(_timed_intervals(events, tz, buffer_minutes)),
            "slots": slots,
        }
    )


def build_executive_briefing(
    *,
    items: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    reminders: list[dict[str, Any]],
    calendar_events: list[dict[str, Any]],
    active_focus: dict[str, Any] | None,
    day: date,
    timezone: str,
    window_days: int,
    include_done: bool = False,
) -> dict[str, Any]:
    tz = ZoneInfo(timezone)
    active_items = [item for item in items if include_done or item.get("status") not in TERMINAL_STATUSES]
    today_items = sorted(
        [item for item in active_items if _item_touches_day(item, day, tz)],
        key=_item_sort_key,
    )[:50]
    overdue_items = sorted(
        [item for item in active_items if _item_is_overdue(item, day, tz)],
        key=_item_sort_key,
    )[:50]
    conflicts = calendar_conflicts(calendar_events, timezone)
    return {
        "generated_at": datetime.now(UTC),
        "timezone": timezone,
        "window": {"date": day, "days": window_days},
        "today_items": today_items,
        "overdue_items": overdue_items,
        "pending_proposals": sorted(proposals, key=lambda row: str(row.get("created_at") or ""), reverse=True)[:50],
        "unread_reminders": reminders,
        "calendar_conflicts": conflicts,
        "focus_status": active_focus,
        "summary": {
            "today_item_count": len(today_items),
            "overdue_item_count": len(overdue_items),
            "pending_proposal_count": len(proposals),
            "unread_reminder_count": len(reminders),
            "calendar_conflict_count": len(conflicts),
            "focus_active": active_focus is not None,
        },
    }


def calendar_conflicts(calendar_events: list[dict[str, Any]], timezone: str) -> list[dict[str, Any]]:
    tz = ZoneInfo(timezone)
    intervals = sorted(_timed_intervals(calendar_events, tz, 0), key=lambda row: (row["start"], row["end"], row["title"]))
    conflicts: list[dict[str, Any]] = []
    for index, current in enumerate(intervals):
        for other in intervals[index + 1 :]:
            if other["start"] >= current["end"]:
                break
            conflicts.append(
                {
                    "start": max(current["start"], other["start"]),
                    "end": min(current["end"], other["end"]),
                    "events": [
                        _event_ref(current),
                        _event_ref(other),
                    ],
                }
            )
    return conflicts[:20]


def build_free_slots(
    *,
    calendar_events: list[dict[str, Any]],
    start_day: date,
    end_day: date,
    timezone: str,
    duration_minutes: int,
    preferred_start: str = "09:00",
    preferred_end: str = "18:00",
    buffer_minutes: int = 0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    tz = ZoneInfo(timezone)
    preferred_start_time = time.fromisoformat(preferred_start)
    preferred_end_time = time.fromisoformat(preferred_end)
    busy = sorted(_timed_intervals(calendar_events, tz, buffer_minutes), key=lambda row: row["start"])
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=30)
    slots: list[dict[str, Any]] = []
    current_day = start_day
    while current_day <= end_day and len(slots) < limit:
        day_start = datetime.combine(current_day, preferred_start_time, tzinfo=tz)
        day_end = datetime.combine(current_day, preferred_end_time, tzinfo=tz)
        if day_end <= day_start:
            day_end += timedelta(days=1)
        cursor = day_start
        while cursor + duration <= day_end and len(slots) < limit:
            slot_end = cursor + duration
            if not _overlaps_any(cursor, slot_end, busy):
                slots.append({"start": cursor, "end": slot_end})
                cursor = slot_end
            else:
                cursor += step
        current_day += timedelta(days=1)
    return slots


def _item_touches_day(item: dict[str, Any], day: date, tz: ZoneInfo) -> bool:
    return any(_value_date(item.get(key), tz) == day for key in ("start_at", "due_at", "start_date", "due_date"))


def _item_is_overdue(item: dict[str, Any], day: date, tz: ZoneInfo) -> bool:
    dates = [_value_date(item.get(key), tz) for key in ("due_at", "due_date", "start_at", "start_date")]
    return any(value is not None and value < day for value in dates)


def _item_sort_key(item: dict[str, Any]) -> tuple[str, str, str]:
    priority_rank = {"urgent": "0", "high": "1", "normal": "2", "low": "3"}.get(str(item.get("priority")), "4")
    schedule = min(
        (str(item.get(key)) for key in ("start_at", "due_at", "start_date", "due_date") if item.get(key)),
        default="9999",
    )
    return (schedule, priority_rank, str(item.get("title") or ""))


def _value_date(value: Any, tz: ZoneInfo) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=tz)
        return parsed.astimezone(tz).date()
    if isinstance(value, date):
        return value
    text = str(value)
    try:
        if "T" in text or " " in text:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=tz)
            return parsed.astimezone(tz).date()
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _timed_intervals(events: list[dict[str, Any]], tz: ZoneInfo, buffer_minutes: int) -> list[dict[str, Any]]:
    buffer = timedelta(minutes=buffer_minutes)
    intervals: list[dict[str, Any]] = []
    for event in events:
        if event.get("all_day"):
            continue
        start = _to_datetime(event.get("start"), tz)
        end = _to_datetime(event.get("end"), tz)
        if start is None:
            continue
        if end is None or end <= start:
            end = start + timedelta(minutes=30)
        intervals.append({**event, "start": start - buffer, "end": end + buffer})
    return intervals


def _to_datetime(value: Any, tz: ZoneInfo) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _event_ref(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id"),
        "kind": event.get("kind"),
        "title": event.get("title"),
        "source_id": event.get("source_id"),
    }


def _overlaps_any(start: datetime, end: datetime, busy: list[dict[str, Any]]) -> bool:
    return any(start < interval["end"] and interval["start"] < end for interval in busy)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value
