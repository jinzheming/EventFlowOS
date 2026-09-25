"""Small, server-side AMap client used for address selection and travel estimates."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from personal_affairs.config import Settings

AMAP_BASE = "https://restapi.amap.com"
HttpGetter = Callable[..., httpx.Response]


@dataclass(frozen=True)
class LocationCandidate:
    name: str
    address: str
    poi_id: str | None
    latitude: float
    longitude: float
    city: str | None = None
    adcode: str | None = None
    confidence: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "poi_id": self.poi_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "city": self.city,
            "adcode": self.adcode,
            "confidence": self.confidence,
            "provider": "amap",
        }


@dataclass(frozen=True)
class RouteEstimate:
    distance_meters: int
    duration_seconds: int
    mode: str
    fetched_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "distance_meters": self.distance_meters,
            "duration_seconds": self.duration_seconds,
            "mode": self.mode,
            "fetched_at": self.fetched_at,
            "provider": "amap",
        }


class AMapClient:
    def __init__(self, cfg: Settings, getter: HttpGetter | None = None):
        self.cfg = cfg
        self._getter = getter or httpx.get

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.amap_enabled and self.cfg.amap_key)

    def resolve(self, query: str, *, city: str | None = None, adcode: str | None = None, limit: int = 5) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "provider": "amap", "candidates": []}
        params: dict[str, Any] = {"key": self.cfg.amap_key, "address": query, "output": "json"}
        if city or self.cfg.amap_default_city:
            params["city"] = city or self.cfg.amap_default_city
        if adcode:
            params["adcode"] = adcode
        try:
            response = self._getter(f"{AMAP_BASE}/v3/geocode/geo", params=params, timeout=self.cfg.amap_timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"status": "error", "provider": "amap", "candidates": [], "error": str(exc)}
        if str(payload.get("status")) != "1":
            return {"status": "error", "provider": "amap", "candidates": [], "error": payload.get("info") or "amap_error"}
        candidates = [_candidate_from_geocode(row) for row in payload.get("geocodes", [])]
        candidates = [candidate for candidate in candidates if candidate is not None][: max(1, min(limit, 20))]
        return {"status": "ok", "provider": "amap", "query": query, "candidates": [c.as_dict() for c in candidates]}

    def search_poi(self, query: str, *, city: str | None = None, limit: int = 5) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "provider": "amap", "candidates": []}
        params: dict[str, Any] = {"key": self.cfg.amap_key, "keywords": query, "output": "json", "offset": max(1, min(limit, 20))}
        if city or self.cfg.amap_default_city:
            params["city"] = city or self.cfg.amap_default_city
        try:
            response = self._getter(f"{AMAP_BASE}/v3/place/text", params=params, timeout=self.cfg.amap_timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"status": "error", "provider": "amap", "candidates": [], "error": str(exc)}
        if str(payload.get("status")) != "1":
            return {"status": "error", "provider": "amap", "candidates": [], "error": payload.get("info") or "amap_error"}
        candidates = [_candidate_from_poi(row) for row in payload.get("pois", [])]
        candidates = [candidate for candidate in candidates if candidate is not None][: max(1, min(limit, 20))]
        return {"status": "ok", "provider": "amap", "query": query, "candidates": [c.as_dict() for c in candidates]}

    def route(self, origin: tuple[float, float], destination: tuple[float, float], mode: str = "transit") -> RouteEstimate | None:
        if not self.enabled:
            return None
        origin_text = f"{origin[0]},{origin[1]}"
        destination_text = f"{destination[0]},{destination[1]}"
        if mode == "driving":
            path = "/v5/direction/driving"
            params = {"origin": origin_text, "destination": destination_text}
        elif mode == "walking":
            path = "/v5/direction/walking"
            params = {"origin": origin_text, "destination": destination_text}
        elif mode == "cycling":
            path = "/v5/direction/bicycling"
            params = {"origin": origin_text, "destination": destination_text}
        else:
            path = "/v3/direction/transit/integrated"
            params = {"origin": origin_text, "destination": destination_text, "city": self.cfg.amap_default_city or "全国", "output": "json"}
        params["key"] = self.cfg.amap_key
        try:
            response = self._getter(f"{AMAP_BASE}{path}", params=params, timeout=self.cfg.amap_timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if str(payload.get("status")) != "1":
            return None
        distance, duration = _route_values(payload)
        if distance is None or duration is None:
            return None
        return RouteEstimate(distance, duration, mode, datetime.now(UTC).isoformat())


def _candidate_from_geocode(row: dict[str, Any]) -> LocationCandidate | None:
    location = str(row.get("location") or "")
    try:
        longitude, latitude = (float(value) for value in location.split(",", 1))
    except (ValueError, TypeError):
        return None
    return LocationCandidate(
        name=str(row.get("building") or row.get("formatted_address") or row.get("level") or "地址"),
        address=str(row.get("formatted_address") or ""),
        poi_id=row.get("adcode"), latitude=latitude, longitude=longitude,
        city=row.get("city") if isinstance(row.get("city"), str) else None,
        adcode=row.get("adcode"), confidence=0.8,
    )


def _candidate_from_poi(row: dict[str, Any]) -> LocationCandidate | None:
    location = str(row.get("location") or "")
    try:
        longitude, latitude = (float(value) for value in location.split(",", 1))
    except (ValueError, TypeError):
        return None
    return LocationCandidate(
        name=str(row.get("name") or "地点"), address=str(row.get("address") or ""),
        poi_id=row.get("id"), latitude=latitude, longitude=longitude,
        city=row.get("cityname"), adcode=row.get("adname"), confidence=0.9,
    )


def _route_values(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    candidates: list[dict[str, Any]] = []
    route = payload.get("route")
    if isinstance(route, dict):
        for key in ("paths", "transits", "taxi"):
            value = route.get(key)
            if isinstance(value, list):
                candidates.extend(row for row in value if isinstance(row, dict))
        if isinstance(route.get("paths"), list):
            candidates.extend(row for row in route["paths"] if isinstance(row, dict))
    candidates.extend(row for row in payload.get("paths", []) if isinstance(row, dict))
    for row in candidates:
        distance = _int_value(row.get("distance"))
        duration = _int_value(row.get("duration"))
        if distance is not None and duration is not None:
            return distance, duration
    return None, None


def _int_value(value: Any) -> int | None:
    try:
        return int(float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None
