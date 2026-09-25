from datetime import datetime
from typing import Any
from uuid import UUID

from personal_affairs.application.location_service import AMapClient
from personal_affairs.storage.repositories.items import ItemsRepository


def assess_schedule_feasibility(
    items: ItemsRepository,
    user_id: UUID,
    item_ids: list[UUID],
    amap: AMapClient,
    *,
    travel_mode: str = "transit",
    buffer_minutes: int = 15,
) -> dict[str, Any]:
    rows = [items.get_item(user_id, item_id) for item_id in item_ids]
    selected = [row for row in rows if row and row.get("start_at") and row.get("due_at")]
    selected.sort(key=lambda row: (row["start_at"], str(row["id"])))
    checks: list[dict[str, Any]] = []
    for previous, current in zip(selected, selected[1:], strict=False):
        checks.append(_assess_pair(previous, current, amap, travel_mode, buffer_minutes))
    critical = any(row["warning_level"] == "critical" for row in checks)
    unknown = any(row["warning_level"] == "unknown" for row in checks)
    return {
        "feasible": not critical and not unknown,
        "warning_level": "critical" if critical else "unknown" if unknown else "ok",
        "travel_mode": travel_mode,
        "buffer_minutes": buffer_minutes,
        "checked_item_ids": [str(row["id"]) for row in selected],
        "skipped_item_ids": [str(row["id"]) for row in rows if row and not (row.get("start_at") and row.get("due_at"))],
        "checks": checks,
    }


def _assess_pair(previous: dict[str, Any], current: dict[str, Any], amap: AMapClient, mode: str, buffer_minutes: int) -> dict[str, Any]:
    start = _datetime(previous["due_at"])
    end = _datetime(current["start_at"])
    available = max(0, int((end - start).total_seconds()))
    preparation = buffer_minutes * 60
    route = None
    unknown_reason: str | None = None
    previous_offline = previous.get("event_format") == "offline"
    current_offline = current.get("event_format") == "offline"
    if previous_offline and current_offline:
        origin = _coordinates(previous)
        destination = _coordinates(current)
        if not origin or not destination:
            unknown_reason = "线下地点尚未解析，无法估计交通时间"
        else:
            route = amap.route(origin, destination, mode)
            if route is None:
                unknown_reason = "地图路线服务不可用，无法估计交通时间"
    elif previous_offline != current_offline:
        unknown_reason = "线上与线下切换缺少可计算的出发地或返回地点"
    required = preparation + (route.duration_seconds if route else 0)
    shortfall = max(0, required - available)
    warning_level = "unknown" if unknown_reason else "critical" if shortfall else "ok"
    if unknown_reason:
        suggestion = unknown_reason + "；请补充地点或手动确认行程。"
    elif shortfall:
        suggestion = "时间不足，建议改期、调整顺序或将其中一项改为线上。"
    else:
        suggestion = "时间和交通缓冲充足。"
    result: dict[str, Any] = {
        "feasible": warning_level == "ok",
        "warning_level": warning_level,
        "from_item": str(previous["id"]),
        "from_title": previous["title"],
        "to_item": str(current["id"]),
        "to_title": current["title"],
        "available_seconds": available,
        "preparation_buffer_seconds": preparation,
        "required_seconds": required,
        "shortfall_seconds": shortfall,
        "suggestion": suggestion,
    }
    if route:
        result.update({"distance_meters": route.distance_meters, "travel_seconds": route.duration_seconds, "route": route.as_dict()})
    if unknown_reason:
        result["reason"] = "location_unknown" if "地点" in unknown_reason else "route_unavailable"
    return result


def _datetime(value: Any) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
    lat, lon = item.get("location_latitude"), item.get("location_longitude")
    if lat is None or lon is None:
        return None
    return float(lon), float(lat)
