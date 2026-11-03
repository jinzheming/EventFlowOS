"""Higher-level calendar planning used by MCP workflows."""

import math
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from psycopg import Connection

from personal_affairs.application.agent_context_service import (
    _json_safe,
    _timed_intervals,
    build_free_slots,
    calendar_conflicts,
)
from personal_affairs.application.calendar_query_service import CalendarQueryService
from personal_affairs.application.location_service import AMapClient, RouteEstimate
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.preferences import PreferencesRepository
from personal_affairs.storage.repositories.projects import ProjectsRepository

TRAVEL_FACTOR = 1.5
TIGHT_SLACK_MINUTES = 15
_TRAVEL_MODES = ("transit", "driving")


def user_timezone(conn: Connection, user_id, fallback: str) -> str:
    return str(PreferencesRepository(conn).get(user_id, fallback).get("timezone") or fallback)


def prepare_event(
    conn: Connection,
    user_id,
    candidate: dict[str, Any],
    amap: AMapClient,
    timezone: str,
) -> dict[str, Any]:
    enriched, location = resolve_event_location(candidate, amap)
    events = _events_around_candidate(conn, user_id, enriched, timezone)
    assessment = assess_candidate(events, enriched, amap, timezone)
    assessment = _mark_location_uncertainty(assessment, location)
    return _json_safe(
        {
            "event": enriched,
            "location_resolution": location,
            "assessment": assessment,
        }
    )


def find_meeting_slots(
    conn: Connection,
    user_id,
    amap: AMapClient,
    timezone: str,
    *,
    duration_minutes: int,
    start_date: str,
    end_date: str,
    event_format: str | None = None,
    location_name: str | None = None,
    location_address: str | None = None,
    location_latitude: float | None = None,
    location_longitude: float | None = None,
    preferred_start: str = "09:00",
    preferred_end: str = "18:00",
    buffer_minutes: int = 0,
    limit: int = 5,
) -> dict[str, Any]:
    tz = ZoneInfo(timezone)
    start_day = date.fromisoformat(start_date)
    end_day = date.fromisoformat(end_date)
    if end_day < start_day:
        start_day, end_day = end_day, start_day
    duration_minutes = max(1, min(duration_minutes, 24 * 60))
    buffer_minutes = max(0, min(buffer_minutes, 24 * 60))
    limit = max(1, min(limit, 100))

    window_start = datetime.combine(start_day - timedelta(days=1), time.min, tzinfo=tz)
    window_end = datetime.combine(end_day + timedelta(days=2), time.min, tzinfo=tz)
    events = _calendar_events(
        conn, user_id, window_start.isoformat(), window_end.isoformat(), timezone
    )
    candidate: dict[str, Any] = {
        "title": "候选会议",
        "all_day": False,
        "event_format": event_format,
        "location_name": location_name,
        "location_address": location_address,
        "location_latitude": location_latitude,
        "location_longitude": location_longitude,
    }
    candidate, location = resolve_event_location(candidate, amap)
    raw_slots = build_free_slots(
        calendar_events=_expand_all_day_events(events, tz),
        start_day=start_day,
        end_day=end_day,
        timezone=timezone,
        duration_minutes=duration_minutes,
        preferred_start=preferred_start,
        preferred_end=preferred_end,
        buffer_minutes=buffer_minutes,
        limit=100,
    )

    route_cache: dict[tuple[tuple[float, float], tuple[float, float], str], RouteEstimate | None] = {}
    slots: list[dict[str, Any]] = []
    rejected_for_travel = 0
    for slot in raw_slots:
        slot_candidate = {
            **candidate,
            "start_at": slot["start"],
            "due_at": slot["end"],
        }
        assessment = assess_candidate(
            events, slot_candidate, amap, timezone, route_cache=route_cache
        )
        if event_format == "offline":
            assessment = _mark_location_uncertainty(assessment, location)
        if assessment["status"] == "travel_blocked":
            rejected_for_travel += 1
            continue
        slots.append(
            {
                "start": slot["start"],
                "end": slot["end"],
                "status": assessment["status"],
                "recommended_travel_mode": assessment["recommended_travel_mode"],
                "travel_modes": assessment["travel_modes"],
                "travel_checks": assessment["travel_checks"],
            }
        )
        if len(slots) >= limit:
            break

    return _json_safe(
        {
            "timezone": timezone,
            "window": {"start_date": start_day, "end_date": end_day},
            "duration_minutes": duration_minutes,
            "buffer_minutes": buffer_minutes,
            "busy_count": len(
                _timed_intervals(_expand_all_day_events(events, tz), tz, buffer_minutes)
            ),
            "event_format": event_format,
            "location_resolution": location,
            "rejected_for_travel": rejected_for_travel,
            "slots": slots,
        }
    )


def get_schedule_summary(
    conn: Connection,
    user_id,
    timezone: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    tz = ZoneInfo(timezone)
    start_day = date.fromisoformat(start_date)
    end_day = date.fromisoformat(end_date)
    if end_day < start_day:
        start_day, end_day = end_day, start_day
    window_start = datetime.combine(start_day, time.min, tzinfo=tz)
    window_end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz)
    events = _calendar_events(
        conn, user_id, window_start.isoformat(), window_end.isoformat(), timezone
    )

    by_day: dict[str, dict[str, int]] = {}
    timed_minutes = 0
    all_day_count = 0
    online_count = 0
    offline_count = 0
    for event in events:
        if event.get("event_format") == "online":
            online_count += 1
        elif event.get("event_format") == "offline":
            offline_count += 1

        if event.get("all_day"):
            all_day_count += 1
            interval = _all_day_interval(event, tz)
            if interval is None:
                continue
            event_start = max(interval[0].date(), start_day)
            event_end = min((interval[1] - timedelta(microseconds=1)).date(), end_day)
            current_day = event_start
            while current_day <= event_end:
                by_day.setdefault(current_day.isoformat(), {"events": 0, "minutes": 0})[
                    "events"
                ] += 1
                current_day += timedelta(days=1)
            continue

        start = _as_datetime(event.get("start"), tz)
        end = _as_datetime(event.get("end"), tz)
        if start is None:
            continue
        if end is None or end <= start:
            end = start + timedelta(minutes=30)
        start = max(start, window_start)
        end = min(end, window_end)
        if end <= start:
            continue
        timed_minutes += math.ceil((end - start).total_seconds() / 60)
        current_day = start.date()
        while current_day <= (end - timedelta(microseconds=1)).date():
            day_start = datetime.combine(current_day, time.min, tzinfo=tz)
            day_end = day_start + timedelta(days=1)
            minutes = math.ceil(
                (min(end, day_end) - max(start, day_start)).total_seconds() / 60
            )
            bucket = by_day.setdefault(current_day.isoformat(), {"events": 0, "minutes": 0})
            bucket["events"] += 1
            bucket["minutes"] += max(0, minutes)
            current_day += timedelta(days=1)

    return _json_safe(
        {
            "timezone": timezone,
            "window": {"start_date": start_day, "end_date": end_day},
            "total_events": len(events),
            "all_day_events": all_day_count,
            "timed_events": len(events) - all_day_count,
            "online_events": online_count,
            "offline_events": offline_count,
            "scheduled_minutes": timed_minutes,
            "conflict_count": len(calendar_conflicts(_expand_all_day_events(events, tz), timezone)),
            "by_day": by_day,
        }
    )


def resolve_event_location(
    candidate: dict[str, Any], amap: AMapClient
) -> tuple[dict[str, Any], dict[str, Any]]:
    enriched = dict(candidate)
    if enriched.get("event_format") != "offline":
        return enriched, {"status": "not_required"}

    latitude = enriched.get("location_latitude")
    longitude = enriched.get("location_longitude")
    if latitude is not None and longitude is not None:
        enriched.setdefault("location_provider", "agent")
        return enriched, {"status": "resolved", "source": "provided"}

    query = (
        enriched.get("location_address")
        or enriched.get("location_name")
        or enriched.get("event_location")
    )
    if not query:
        return enriched, {"status": "missing"}
    if not amap.enabled:
        return enriched, {"status": "disabled", "query": query}

    poi_result = amap.search_poi(str(query), limit=5)
    candidates = poi_result.get("candidates", [])
    exact = _exact_location_matches(str(query), candidates)
    selected = exact[0] if len(exact) == 1 else candidates[0] if len(candidates) == 1 else None
    if selected is None and not candidates:
        geo_result = amap.resolve(str(query), limit=5)
        candidates = geo_result.get("candidates", [])
        exact = _exact_location_matches(str(query), candidates)
        selected = exact[0] if len(exact) == 1 else candidates[0] if len(candidates) == 1 else None

    if selected is None:
        return enriched, {
            "status": "ambiguous" if candidates else "unresolved",
            "query": query,
            "candidates": candidates[:5],
        }

    enriched.update(
        {
            "location_name": enriched.get("location_name") or selected.get("name"),
            "location_address": enriched.get("location_address") or selected.get("address"),
            "location_provider": selected.get("provider", "amap"),
            "location_poi_id": selected.get("poi_id"),
            "location_latitude": selected.get("latitude"),
            "location_longitude": selected.get("longitude"),
            "location_confidence": selected.get("confidence"),
        }
    )
    return enriched, {"status": "resolved", "source": "amap", "candidate": selected}


def assess_candidate(
    calendar_events: list[dict[str, Any]],
    candidate: dict[str, Any],
    amap: AMapClient,
    timezone: str,
    *,
    route_cache: dict[
        tuple[tuple[float, float], tuple[float, float], str], RouteEstimate | None
    ]
    | None = None,
) -> dict[str, Any]:
    tz = ZoneInfo(timezone)
    interval = _candidate_interval(candidate, tz)
    if interval is None:
        raise ValueError(
            "Provide a valid timed start_at/due_at or all-day start_date/due_date."
        )
    start, end = interval

    busy = _timed_intervals(calendar_events, tz, 0)
    overlaps = [
        _event_reference(event)
        for event in busy
        if start < event["end"] and event["start"] < end
    ]
    for event in calendar_events:
        if event.get("all_day") and _intervals_overlap(
            (start, end), _all_day_interval(event, tz)
        ):
            overlaps.append(_event_reference(event))

    travel_checks: list[dict[str, Any]] = []
    if candidate.get("event_format") == "offline" and not candidate.get("all_day"):
        travel_candidate = {**candidate, "start": start, "end": end}
        previous = [
            event
            for event in busy
            if event["end"] <= start and _is_physical_event(event)
        ]
        following = [
            event
            for event in busy
            if event["start"] >= end and _is_physical_event(event)
        ]
        previous_event = max(previous, key=lambda event: event["end"], default=None)
        next_event = min(following, key=lambda event: event["start"], default=None)
        if previous_event:
            travel_checks.append(
                _assess_travel_leg(
                    previous_event, travel_candidate, "to_candidate", amap, route_cache
                )
            )
        if next_event:
            travel_checks.append(
                _assess_travel_leg(
                    travel_candidate, next_event, "from_candidate", amap, route_cache
                )
            )

    travel_modes = _summarize_modes(travel_checks)
    recommended = _recommended_mode(travel_modes)
    if overlaps:
        status = "conflict"
        recommendation = "与现有日程重叠；请先调整时间再创建。"
    elif any(mode["status"] == "ok" for mode in travel_modes.values()):
        status = "travel_warning" if any(
            mode["status"] in {"tight", "impossible", "unknown"}
            for mode in travel_modes.values()
        ) else "ready"
        recommendation = (
            f"交通方式建议：{'公交' if recommended == 'transit' else '驾车'}。"
            if status == "travel_warning" and recommended
            else "日程没有直接冲突，已检查可计算的路程。"
        )
    elif any(mode["status"] == "tight" for mode in travel_modes.values()):
        status = "travel_warning"
        recommendation = "交通时间较紧；建议选择余量更大的方式，或提前出发。"
    elif all(
        travel_modes[mode]["status"] == "impossible" for mode in _TRAVEL_MODES
    ):
        status = "travel_blocked"
        recommendation = "两种交通方式的路程缓冲都不足；建议改期或改为线上。"
    elif any(mode["status"] == "unknown" for mode in travel_modes.values()):
        status = "travel_unknown"
        recommendation = "相邻日程地点或路线信息不足，不能确认路程；请补充地点后再判断。"
    else:
        status = "ready"
        recommendation = "日程没有直接冲突。"

    return {
        "status": status,
        "timezone": timezone,
        "overlaps": overlaps,
        "travel_factor": TRAVEL_FACTOR,
        "tight_slack_minutes": TIGHT_SLACK_MINUTES,
        "travel_checks": travel_checks,
        "travel_modes": travel_modes,
        "recommended_travel_mode": recommended,
        "recommendation": recommendation,
    }


def _assess_travel_leg(
    origin_event: dict[str, Any],
    destination_event: dict[str, Any],
    leg: str,
    amap: AMapClient,
    route_cache: dict[
        tuple[tuple[float, float], tuple[float, float], str], RouteEstimate | None
    ]
    | None,
) -> dict[str, Any]:
    available_seconds = max(
        0,
        int((destination_event["start"] - origin_event["end"]).total_seconds()),
    )
    origin = _coordinates(origin_event)
    destination = _coordinates(destination_event)
    if not origin or not destination:
        return {
            "leg": leg,
            "from_title": origin_event.get("title"),
            "to_title": destination_event.get("title"),
            "available_minutes": available_seconds // 60,
            "modes": {
                mode: {"status": "unknown", "reason": "location_missing"}
                for mode in _TRAVEL_MODES
            },
        }

    modes: dict[str, dict[str, Any]] = {}
    for mode in _TRAVEL_MODES:
        key = (origin, destination, mode)
        route = route_cache.get(key) if route_cache is not None and key in route_cache else None
        if route_cache is None or key not in route_cache:
            route = amap.route(origin, destination, mode)
            if route_cache is not None:
                route_cache[key] = route
        if route is None:
            modes[mode] = {"status": "unknown", "reason": "route_unavailable"}
            continue
        buffered_seconds = math.ceil(route.duration_seconds * TRAVEL_FACTOR)
        slack_seconds = available_seconds - buffered_seconds
        status = (
            "impossible"
            if slack_seconds < 0
            else "tight"
            if slack_seconds < TIGHT_SLACK_MINUTES * 60
            else "ok"
        )
        modes[mode] = {
            "status": status,
            "distance_meters": route.distance_meters,
            "estimated_minutes": math.ceil(route.duration_seconds / 60),
            "buffered_minutes": math.ceil(buffered_seconds / 60),
            "available_minutes": available_seconds // 60,
            "slack_minutes": math.floor(slack_seconds / 60),
            "fetched_at": route.fetched_at,
        }

    return {
        "leg": leg,
        "from_title": origin_event.get("title"),
        "to_title": destination_event.get("title"),
        "available_minutes": available_seconds // 60,
        "modes": modes,
    }


def _summarize_modes(checks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for mode in _TRAVEL_MODES:
        legs = [check["modes"][mode] for check in checks]
        if not legs:
            summary[mode] = {"status": "not_required"}
            continue
        statuses = {leg["status"] for leg in legs}
        status = (
            "impossible"
            if "impossible" in statuses
            else "tight"
            if "tight" in statuses
            else "unknown"
            if "unknown" in statuses
            else "ok"
        )
        slack = [leg["slack_minutes"] for leg in legs if "slack_minutes" in leg]
        summary[mode] = {
            "status": status,
            "minimum_slack_minutes": min(slack) if slack else None,
        }
    return summary


def _recommended_mode(modes: dict[str, dict[str, Any]]) -> str | None:
    ranked = [
        (details["minimum_slack_minutes"], mode)
        for mode, details in modes.items()
        if details.get("minimum_slack_minutes") is not None
        and details.get("status") in {"ok", "tight"}
    ]
    return max(ranked, default=(None, None))[1]


def _mark_location_uncertainty(
    assessment: dict[str, Any], location: dict[str, Any]
) -> dict[str, Any]:
    if assessment["status"] == "conflict":
        return assessment
    if location.get("status") == "ambiguous":
        return {
            **assessment,
            "status": "location_ambiguous",
            "recommendation": "地点匹配到多个候选，请先确认具体地点。",
        }
    if location.get("status") in {"disabled", "unresolved", "error"}:
        return {
            **assessment,
            "status": "travel_unknown",
            "recommendation": "地点或路线无法确认；请补充地址，或确认后接受路线未知再创建。",
        }
    return assessment


def _events_around_candidate(
    conn: Connection, user_id, candidate: dict[str, Any], timezone: str
) -> list[dict[str, Any]]:
    tz = ZoneInfo(timezone)
    interval = _candidate_interval(candidate, tz)
    if interval is None:
        raise ValueError("Candidate event must have a valid start and end.")
    start, end = interval
    window_start = start - timedelta(days=1)
    window_end = end + timedelta(days=1)
    return _calendar_events(
        conn, user_id, window_start.isoformat(), window_end.isoformat(), timezone
    )


def _calendar_events(
    conn: Connection, user_id, start: str, end: str, timezone: str
) -> list[dict[str, Any]]:
    events = CalendarQueryService(
        ItemsRepository(conn), ProjectsRepository(conn)
    ).events(user_id, start, end, {"work_item", "personal_item"})
    tz = ZoneInfo(timezone)
    window_start = _as_datetime(start, tz)
    window_end = _as_datetime(end, tz)
    if window_start is None or window_end is None:
        return events
    result = []
    for event in events:
        if event.get("all_day"):
            interval = _all_day_interval(event, tz)
        else:
            event_start = _as_datetime(event.get("start"), tz)
            if event_start is None:
                continue
            event_end = _as_datetime(event.get("end"), tz)
            if event_end is None or event_end <= event_start:
                event_end = event_start + timedelta(minutes=30)
            interval = (event_start, event_end)
        if interval and _intervals_overlap(interval, (window_start, window_end)):
            result.append(event)
    return result


def _exact_location_matches(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = _normalize_location(query)
    return [
        candidate
        for candidate in candidates
        if normalized
        and normalized
        in {
            _normalize_location(str(candidate.get("name") or "")),
            _normalize_location(str(candidate.get("address") or "")),
        }
    ]


def _normalize_location(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()


def _coordinates(event: dict[str, Any]) -> tuple[float, float] | None:
    latitude = event.get("location_latitude")
    longitude = event.get("location_longitude")
    if latitude is None or longitude is None:
        return None
    return float(longitude), float(latitude)


def _is_physical_event(event: dict[str, Any]) -> bool:
    if event.get("event_format") == "online":
        return False
    return bool(
        event.get("event_format") == "offline"
        or _coordinates(event)
        or event.get("location_name")
        or event.get("location_address")
        or event.get("event_location")
    )


def _event_reference(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(event.get("source_id") or event.get("id") or ""),
        "title": event.get("title"),
        "start": _json_safe(event.get("start")),
        "end": _json_safe(event.get("end")),
    }


def _candidate_interval(
    candidate: dict[str, Any], timezone: ZoneInfo
) -> tuple[datetime, datetime] | None:
    if candidate.get("all_day"):
        start_day = _as_date(candidate.get("start_date"))
        end_day = _as_date(candidate.get("due_date")) or start_day
        if start_day is None or end_day is None or end_day < start_day:
            return None
        return (
            datetime.combine(start_day, time.min, tzinfo=timezone),
            datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=timezone),
        )
    start = _as_datetime(candidate.get("start_at"), timezone)
    end = _as_datetime(candidate.get("due_at"), timezone)
    if start is None or end is None or end <= start:
        return None
    return start, end


def _all_day_interval(
    event: dict[str, Any], timezone: ZoneInfo
) -> tuple[datetime, datetime] | None:
    start_value = event.get("start_date", event.get("start"))
    end_value = event.get("end_date", event.get("end")) or start_value
    start_day = _date_in_timezone(start_value, timezone)
    end_day = _date_in_timezone(end_value, timezone)
    if start_day is None or end_day is None or end_day < start_day:
        return None
    return (
        datetime.combine(start_day, time.min, tzinfo=timezone),
        datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=timezone),
    )


def _date_in_timezone(value: Any, timezone: ZoneInfo) -> date | None:
    if isinstance(value, datetime):
        parsed = _as_datetime(value, timezone)
        return parsed.date() if parsed else None
    return _as_date(value)


def _intervals_overlap(
    first: tuple[datetime, datetime],
    second: tuple[datetime, datetime] | None,
) -> bool:
    return bool(second and first[0] < second[1] and second[0] < first[1])


def _expand_all_day_events(
    events: list[dict[str, Any]], timezone: ZoneInfo
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for event in events:
        if not event.get("all_day"):
            expanded.append(event)
            continue
        interval = _all_day_interval(event, timezone)
        if interval is None:
            continue
        expanded.append(
            {**event, "all_day": False, "start": interval[0], "end": interval[1]}
        )
    return expanded


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _as_datetime(value: Any, timezone: ZoneInfo) -> datetime | None:
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
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)
