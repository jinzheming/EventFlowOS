from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from psycopg import Connection

from personal_affairs.config import Settings
from personal_affairs.domain.enums import ItemScope, ItemStatus, Priority
from personal_affairs.domain.errors import DomainError
from personal_affairs.domain.models import ItemSchedule
from personal_affairs.domain.policies import validate_schedule
from personal_affairs.storage.repositories.people import PeopleRepository
from personal_affairs.storage.repositories.projects import ProjectsRepository
from personal_affairs.storage.repositories.tags import TagsRepository

logger = logging.getLogger(__name__)

_META_KEYS = {"intake_text", "intake_scope_source", "intake_origin", "intake_normalization"}
_SCOPE_CHOICES = {"work", "personal"}
_STATUS_CHOICES = {"inbox", "planned", "in_progress", "waiting"}
_PRIORITY_CHOICES = {"low", "normal", "high", "urgent"}
_PERSON_ROLE_CHOICES = {"together", "waiting"}
_RECURRENCE_CHOICES = {"daily", "weekly", "monthly"}


class ChatClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> httpx.Response: ...


@dataclass(frozen=True)
class IntakeContext:
    timezone: str
    now: str
    projects: list[dict[str, Any]]
    people: list[dict[str, Any]]
    tags: list[dict[str, Any]]


def _clean_name(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).casefold()


def _row_by_name(rows: list[dict[str, Any]], name: str | None) -> dict[str, Any] | None:
    key = _clean_name(name)
    if not key:
        return None
    for row in rows:
        if _clean_name(row.get("name")) == key:
            return row
    return None


def _choice(data: dict[str, Any], key: str, allowed: set[str]) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized if normalized in allowed else None


def _text(data: dict[str, Any], key: str, max_len: int) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized or len(normalized) > max_len:
        return None
    return normalized


def _confidence(data: dict[str, Any]) -> float:
    try:
        return float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _positive_int(data: dict[str, Any], key: str, upper: int) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 1 or parsed > upper:
        return None
    return parsed


def _bool_or_none(data: dict[str, Any], key: str) -> bool | None:
    value = data.get(key)
    return value if isinstance(value, bool) else None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _has_schedule(payload: dict[str, Any]) -> bool:
    return any(payload.get(key) for key in ("start_at", "due_at", "start_date", "due_date"))


def _valid_schedule(schedule: dict[str, Any]) -> bool:
    try:
        validate_schedule(
            ItemSchedule(
                all_day=schedule.get("all_day", True),
                start_at=schedule.get("start_at"),
                due_at=schedule.get("due_at"),
                start_date=schedule.get("start_date"),
                due_date=schedule.get("due_date"),
            )
        )
    except DomainError:
        return False
    return True


def _context_today(context: IntakeContext) -> date:
    try:
        parsed = datetime.fromisoformat(context.now)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(ZoneInfo(context.timezone))
        return parsed.date()
    except (TypeError, ValueError):
        return datetime.now(ZoneInfo(context.timezone)).date()


def _resolve_month_day(today: date, month: int, day: int) -> date | None:
    candidates: list[date] = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    recent_past = [candidate for candidate in candidates if 0 <= (today - candidate).days <= 7]
    if recent_past:
        return max(recent_past)
    future = [candidate for candidate in candidates if candidate >= today]
    return min(future) if future else None


def _schedule_dates(schedule: dict[str, Any]) -> list[date]:
    dates: list[date] = []
    for key in ("start_date", "due_date"):
        value = schedule.get(key)
        if isinstance(value, date) and not isinstance(value, datetime):
            dates.append(value)
    for key in ("start_at", "due_at"):
        value = schedule.get(key)
        if isinstance(value, datetime):
            dates.append(value.date())
    return dates


def _schedule_matches_source_text(schedule: dict[str, Any], source_text: str, context: IntakeContext) -> bool:
    if not source_text:
        return True
    dates = _schedule_dates(schedule)
    if not dates:
        return True
    today = _context_today(context)
    if re.search(r"大前天|前天|昨天|昨日|上周", source_text) and any(value > today for value in dates):
        return False

    expected_month_days: list[date] = []
    for match in re.finditer(r"(?<![\d年])(\d{1,2})月(\d{1,2})[日号]", source_text):
        resolved = _resolve_month_day(today, int(match.group(1)), int(match.group(2)))
        if resolved:
            expected_month_days.append(resolved)
    return not expected_month_days or any(value in expected_month_days for value in dates)


def _scope_value(value: Any) -> str:
    return value.value if isinstance(value, ItemScope) else str(value)


def _status_value(value: Any) -> str:
    return value.value if isinstance(value, ItemStatus) else str(value)


def _priority_value(value: Any) -> str:
    return value.value if isinstance(value, Priority) else str(value)


def _set_if_changed(payload: dict[str, Any], key: str, value: Any, changed: set[str]) -> None:
    if payload.get(key) != value:
        payload[key] = value
        changed.add(key)


def apply_item_intake_suggestion(
    payload: dict[str, Any],
    suggestion: dict[str, Any],
    context: IntakeContext,
    *,
    model: str,
    min_confidence: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    normalized = {key: value for key, value in payload.items() if key not in _META_KEYS}
    if _confidence(suggestion) < min_confidence:
        return normalized, None

    changed: set[str] = set()
    intake_text = str(payload.get("intake_text") or "").strip()
    scope_source = str(payload.get("intake_scope_source") or "").strip()
    current_status = _status_value(normalized.get("status", "inbox"))

    title = _text(suggestion, "title", 500)
    if title and intake_text:
        _set_if_changed(normalized, "title", title, changed)

    suggested_scope = _choice(suggestion, "scope", _SCOPE_CHOICES)
    scope_locked = scope_source in {"explicit", "identity"} or normalized.get("project_id") is not None
    if suggested_scope and not scope_locked and current_status == "inbox":
        _set_if_changed(normalized, "scope", suggested_scope, changed)

    suggested_status = _choice(suggestion, "status", _STATUS_CHOICES)
    if suggested_status and current_status in {"inbox", "planned"}:
        _set_if_changed(normalized, "status", suggested_status, changed)

    suggested_priority = _choice(suggestion, "priority", _PRIORITY_CHOICES)
    if suggested_priority and _priority_value(normalized.get("priority", "normal")) == "normal":
        _set_if_changed(normalized, "priority", suggested_priority, changed)

    if not _has_schedule(normalized):
        all_day = _bool_or_none(suggestion, "all_day")
        start_at = _parse_datetime(suggestion.get("start_at"))
        due_at = _parse_datetime(suggestion.get("due_at"))
        start_date = _parse_date(suggestion.get("start_date"))
        due_date = _parse_date(suggestion.get("due_date"))
        schedule: dict[str, Any] | None = None
        if all_day is False and (start_at or due_at):
            schedule = {"all_day": False, "start_at": start_at, "due_at": due_at, "start_date": None, "due_date": None}
        elif (all_day is True or not (start_at or due_at)) and (start_date or due_date):
            schedule = {"all_day": True, "start_at": None, "due_at": None, "start_date": start_date, "due_date": due_date}
        if schedule and _valid_schedule(schedule) and _schedule_matches_source_text(schedule, intake_text, context):
            for key, value in schedule.items():
                _set_if_changed(normalized, key, value, changed)

    estimated_minutes = _positive_int(suggestion, "estimated_minutes", 10080)
    if estimated_minutes and not normalized.get("estimated_minutes"):
        _set_if_changed(normalized, "estimated_minutes", estimated_minutes, changed)

    recurrence_freq = _choice(suggestion, "recurrence_freq", _RECURRENCE_CHOICES)
    if recurrence_freq and not normalized.get("recurrence_freq"):
        _set_if_changed(normalized, "recurrence_freq", recurrence_freq, changed)
        interval = _positive_int(suggestion, "recurrence_interval", 99) or 1
        _set_if_changed(normalized, "recurrence_interval", interval, changed)
        recurrence_until = _parse_date(suggestion.get("recurrence_until"))
        recurrence_count = _positive_int(suggestion, "recurrence_count", 999)
        if recurrence_until:
            _set_if_changed(normalized, "recurrence_until", recurrence_until, changed)
        elif recurrence_count:
            _set_if_changed(normalized, "recurrence_count", recurrence_count, changed)

    if not normalized.get("project_id") and _scope_value(normalized.get("scope")) == "work":
        project = _row_by_name(context.projects, _text(suggestion, "project_name", 300))
        if project:
            _set_if_changed(normalized, "project_id", project["id"], changed)

    if not normalized.get("people"):
        person_name = _text(suggestion, "person_name", 120) or _text(suggestion, "waiting_on", 300)
        person_role = _choice(suggestion, "person_role", _PERSON_ROLE_CHOICES)
        person = _row_by_name(context.people, person_name)
        if person and person_role:
            _set_if_changed(normalized, "people", [{"person_id": person["id"], "role": person_role}], changed)
        elif person_name and person_role == "waiting" and not normalized.get("waiting_on"):
            _set_if_changed(normalized, "waiting_on", person_name, changed)
            if _status_value(normalized.get("status", "planned")) not in {"done", "cancelled"}:
                _set_if_changed(normalized, "status", "waiting", changed)

    if not normalized.get("tag_ids"):
        tag_ids: list[UUID] = []
        for name in suggestion.get("tag_names") or []:
            tag = _row_by_name(context.tags, str(name))
            if tag and tag["id"] not in tag_ids:
                tag_ids.append(tag["id"])
        if tag_ids:
            _set_if_changed(normalized, "tag_ids", tag_ids, changed)

    if not changed:
        return normalized, None
    return normalized, {
        "method": "llm_flash",
        "model": model,
        "changed_fields": sorted(changed),
        "confidence": round(_confidence(suggestion), 3),
    }


class ItemIntakeNormalizer:
    def __init__(self, settings: Settings, client: ChatClient | None = None):
        self.settings = settings
        self.client = client

    def normalize(self, user_id: UUID, conn: Connection, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        stripped = {key: value for key, value in payload.items() if key not in _META_KEYS}
        source_text = str(payload.get("intake_text") or payload.get("title") or "").strip()
        if not self.settings.intake_normalization_enabled or not source_text:
            return stripped, None
        if not self.settings.intake_normalization_api_key or not self.settings.intake_normalization_base_url:
            return stripped, None
        try:
            context = self._context(user_id, conn)
            suggestion = self._request_suggestion(source_text, payload, context)
            return apply_item_intake_suggestion(
                payload,
                suggestion,
                context,
                model=self.settings.intake_normalization_model,
                min_confidence=self.settings.intake_normalization_min_confidence,
            )
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            logger.warning("item intake normalization skipped after %s", exc.__class__.__name__)
            return stripped, None

    def _context(self, user_id: UUID, conn: Connection) -> IntakeContext:
        now = datetime.now(ZoneInfo(self.settings.default_timezone)).isoformat()
        return IntakeContext(
            timezone=self.settings.default_timezone,
            now=now,
            projects=[
                {"id": row["id"], "name": row["name"], "status": row["status"]}
                for row in ProjectsRepository(conn).list_projects(user_id, include_archived=False, limit=80)
            ],
            people=[
                {"id": row["id"], "name": row["name"], "identity": row.get("identity")}
                for row in PeopleRepository(conn).list_people(user_id, include_inactive=False)
            ],
            tags=[{"id": row["id"], "name": row["name"]} for row in TagsRepository(conn).list_tags(user_id)],
        )

    def _request_suggestion(self, source_text: str, payload: dict[str, Any], context: IntakeContext) -> dict[str, Any]:
        body = {
            "model": self.settings.intake_normalization_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source_text": source_text,
                            "current_payload": _json_safe_payload(payload),
                            "timezone": context.timezone,
                            "now": context.now,
                            "projects": [{"id": str(p["id"]), "name": p["name"]} for p in context.projects],
                            "people": [{"id": str(p["id"]), "name": p["name"], "identity": p.get("identity")} for p in context.people],
                            "tags": [{"id": str(t["id"]), "name": t["name"]} for t in context.tags],
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                },
            ],
        }
        url = f"{self.settings.intake_normalization_base_url.rstrip('/')}/chat/completions"
        headers = {"authorization": f"Bearer {self.settings.intake_normalization_api_key}"}
        if self.client:
            response = self.client.post(url, headers=headers, json=body, timeout=self.settings.intake_normalization_timeout_seconds)
        else:
            with httpx.Client() as client:
                response = client.post(url, headers=headers, json=body, timeout=self.settings.intake_normalization_timeout_seconds)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _loads_json_object(content)


def _json_safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        if key in {"client_request_id"}:
            continue
        if hasattr(value, "value"):
            safe[key] = value.value
        elif isinstance(value, datetime | date | UUID):
            safe[key] = str(value)
        elif isinstance(value, list):
            safe[key] = [str(item) if isinstance(item, UUID) else item for item in value]
        else:
            safe[key] = value
    return safe


def _loads_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).removesuffix("```").strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("normalization response is not a JSON object")
    return parsed


_SYSTEM_PROMPT = """你是 Personal Affairs 新建事项归一化器。只返回 JSON 对象，不要解释。

目标：把自由文本事项归一化为结构化字段。你是信息抽取器，不是任务规划器。

严格约束：
- 只能根据 source_text 和 current_payload 中明确出现的信息输出判断。
- 不得自行增加用户没有提供的信息，包括日期、时间、scope、项目、人员、标签、优先级、状态、时长、提醒和重复规则。
- 不确定时返回 null、空数组或保留原值。
- 用户已经结构化提供的字段不要覆盖。
- 相对日期必须以 now 和 timezone 为基准；昨天、前天、上周等过去语义不得解析为未来日期。
- 无年份日期只有在用户明确写出月/日/号时才可解析，不得从标题含义猜日期。
- 不要编造不存在的项目、人员或标签。

返回字段：
- title: 精简后的事项标题，去掉明显的日期、时间、提醒、重复、scope 标记。
- scope: work 或 personal；只有 source_text 或 current_payload 明确提供时填写，否则 null。
- status: planned 或 waiting；只有明确排期/计划时用 planned，明确等待他人时用 waiting，否则 null。
- priority: low、normal、high、urgent；只有文本明确紧急/重要/低优先级时填写，否则 null。
- all_day: true/false/null。
- start_at/due_at: 定时事项 ISO datetime，带时区。
- start_date/due_date: 全天事项 YYYY-MM-DD。
- estimated_minutes: 预计分钟数。
- recurrence_freq: daily、weekly、monthly 或 null。
- recurrence_interval、recurrence_until、recurrence_count。
- project_name: 只能使用候选 projects 里的精确项目名，否则 null。
- person_name/person_role: 只能使用候选 people 里的精确姓名；等待他人用 role=waiting，协作用 together。
- waiting_on: 等待对象未在 people 中时可填短姓名/对象。
- tag_names: 只能使用候选 tags 里的精确标签名。
- confidence: 0 到 1。

原则：用户已经结构化提供的字段不要随意覆盖；没有明确证据时返回 null 或空数组。"""
