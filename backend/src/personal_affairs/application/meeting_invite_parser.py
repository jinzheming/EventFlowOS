import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MeetingInviteParseResult:
    title: str | None
    start_at: str | None
    due_at: str | None
    estimated_minutes: int | None
    meeting_id: str | None
    meeting_code: str | None
    join_url: str | None
    notes: str
    missing_fields: list[str]
    confidence: float

    @property
    def proposed_item(self) -> dict:
        payload: dict = {
            "title": self.title or "腾讯会议",
            "scope": "work",
            "status": "planned" if self.start_at or self.due_at else "inbox",
            "priority": "normal",
            "all_day": not (self.start_at or self.due_at),
            "notes": self.notes,
        }
        if self.start_at:
            payload["start_at"] = self.start_at
        if self.due_at:
            payload["due_at"] = self.due_at
        if self.estimated_minutes:
            payload["estimated_minutes"] = self.estimated_minutes
        return payload


def parse_tencent_meeting_invite(raw_text: str, timezone: str = "Asia/Shanghai") -> MeetingInviteParseResult:
    text = raw_text.strip()
    title = _extract_title(text)
    start_at, due_at, estimated_minutes = _extract_schedule(text, timezone)
    meeting_id = _extract_meeting_id(text)
    meeting_code = _extract_meeting_code(text)
    join_url = _extract_join_url(text)
    notes = _format_notes(text, meeting_id, meeting_code, join_url)
    missing = []
    if not title:
        missing.append("title")
    if not start_at or not due_at:
        missing.append("schedule")
    if not meeting_id and not join_url:
        missing.append("meeting_identifier")
    confidence = _confidence(title, start_at, due_at, meeting_id, join_url)
    return MeetingInviteParseResult(
        title=title,
        start_at=start_at,
        due_at=due_at,
        estimated_minutes=estimated_minutes,
        meeting_id=meeting_id,
        meeting_code=meeting_code,
        join_url=join_url,
        notes=notes,
        missing_fields=missing,
        confidence=confidence,
    )


def merge_tmeet_meeting_details(
    parsed: MeetingInviteParseResult,
    details: dict[str, Any],
    timezone: str = "Asia/Shanghai",
) -> MeetingInviteParseResult:
    title = parsed.title or _first_text(details, "subject", "title", "topic", "meeting_subject")
    start_at = parsed.start_at or _coerce_datetime(
        _first_value(details, "start_time", "start_at", "start", "startTime"), timezone
    )
    due_at = parsed.due_at or _coerce_datetime(
        _first_value(details, "end_time", "due_at", "end", "endTime"), timezone
    )
    estimated_minutes = parsed.estimated_minutes or _estimated_minutes(start_at, due_at)
    meeting_id = parsed.meeting_id or _normalize_digits(
        _first_text(details, "meeting_id", "meetingId", "meeting_number", "meetingNumber")
    )
    meeting_code = parsed.meeting_code or _first_text(details, "meeting_code", "password", "pwd")
    join_url = parsed.join_url or _first_text(details, "join_url", "joinUrl", "meeting_url", "meetingUrl")
    notes = _format_notes("", meeting_id, meeting_code, join_url)
    missing = []
    if not title:
        missing.append("title")
    if not start_at or not due_at:
        missing.append("schedule")
    if not meeting_id and not join_url:
        missing.append("meeting_identifier")
    confidence = max(parsed.confidence, _confidence(title, start_at, due_at, meeting_id, join_url))
    return MeetingInviteParseResult(
        title=title,
        start_at=start_at,
        due_at=due_at,
        estimated_minutes=estimated_minutes,
        meeting_id=meeting_id,
        meeting_code=meeting_code,
        join_url=join_url,
        notes=notes,
        missing_fields=missing,
        confidence=confidence,
    )


def _extract_title(text: str) -> str | None:
    patterns = [
        r"会议主题[：:]\s*(.+)",
        r"主题[：:]\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _clean_line(match.group(1))
    return None


def _extract_schedule(text: str, timezone: str) -> tuple[str | None, str | None, int | None]:
    match = re.search(
        r"会议时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s+(\d{1,2}:\d{2})\s*[-~至]\s*(?:(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s+)?(\d{1,2}:\d{2})",
        text,
    )
    if not match:
        return None, None, None
    start_date = match.group(1).replace("/", "-")
    start_time = match.group(2)
    end_date = (match.group(3) or start_date).replace("/", "-")
    end_time = match.group(4)
    tz = ZoneInfo(timezone)
    start = _parse_local_datetime(start_date, start_time, tz)
    end = _parse_local_datetime(end_date, end_time, tz)
    minutes = max(1, int((end - start).total_seconds() // 60)) if end >= start else None
    return start.isoformat(), end.isoformat(), minutes


def _parse_local_datetime(day: str, clock: str, tz: ZoneInfo) -> datetime:
    year, month, date_part = (int(part) for part in day.split("-"))
    hour, minute = (int(part) for part in clock.split(":"))
    return datetime(year, month, date_part, hour, minute, tzinfo=tz)


def _extract_meeting_id(text: str) -> str | None:
    match = re.search(r"会议(?:号|ID|id)[：:]?\s*([0-9][0-9\-\s]{5,})", text)
    if match:
        return _normalize_digits(match.group(1))
    compact = text.strip()
    if re.fullmatch(r"[0-9][0-9\-\s]{5,}", compact):
        return _normalize_digits(compact)
    return None


def _extract_meeting_code(text: str) -> str | None:
    match = re.search(r"(?:密码|会议密码|入会密码)[：:]?\s*([A-Za-z0-9]{2,20})", text)
    return match.group(1) if match else None


def _extract_join_url(text: str) -> str | None:
    match = re.search(r"https://meeting\.tencent\.com/\S+", text)
    if not match:
        return None
    return match.group(0).rstrip("，。,)）]")


def _format_notes(raw_text: str, meeting_id: str | None, meeting_code: str | None, join_url: str | None) -> str:
    lines = ["腾讯会议"]
    if join_url:
        lines.append(f"入会链接：{join_url}")
    if meeting_id:
        lines.append(f"会议号：{meeting_id}")
    if meeting_code:
        lines.append(f"密码：{meeting_code}")
    if not any((join_url, meeting_id, meeting_code)):
        lines.append(_clean_line(raw_text)[:200])
    return "\n".join(lines).strip()


def _confidence(title: str | None, start_at: str | None, due_at: str | None, meeting_id: str | None, join_url: str | None) -> float:
    score = 0.2
    if title:
        score += 0.25
    if start_at and due_at:
        score += 0.3
    if meeting_id:
        score += 0.15
    if join_url:
        score += 0.1
    return min(score, 1.0)


def _clean_line(value: str) -> str:
    return value.strip().splitlines()[0].strip()


def _first_text(details: dict[str, Any], *keys: str) -> str | None:
    value = _first_value(details, *keys)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_value(details: dict[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if details.get(key) not in {None, ""}:
            return details[key]
    return None


def _normalize_digits(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\D", "", value)
    return normalized or None


def _coerce_datetime(value: Any | None, timezone: str) -> str | None:
    if value is None or value == "":
        return None
    tz = ZoneInfo(timezone)
    if isinstance(value, int | float):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=tz).isoformat()
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return _coerce_datetime(int(text), timezone)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.isoformat()


def _estimated_minutes(start_at: str | None, due_at: str | None) -> int | None:
    if not start_at or not due_at:
        return None
    try:
        start = datetime.fromisoformat(start_at)
        end = datetime.fromisoformat(due_at)
    except ValueError:
        return None
    if end < start:
        return None
    return max(1, int((end - start).total_seconds() // 60))
