"""ICS feed builder: read-only VCALENDAR over items + milestones.

Sync semantics: stable UID per record, SEQUENCE tracks item.version, updates
and deletions propagate on the client's next poll (REFRESH-INTERVAL hint).
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg import Connection

PRODID = "-//personal-affairs//CN"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _utc_stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _date_stamp(value: date) -> str:
    return value.strftime("%Y%m%d")


def _rrule(item: dict) -> str | None:
    freq = item.get("recurrence_freq")
    if not freq:
        return None
    parts = [f"FREQ={freq.upper()}"]
    if item.get("recurrence_interval") and item["recurrence_interval"] > 1:
        parts.append(f"INTERVAL={item['recurrence_interval']}")
    if item.get("recurrence_until"):
        parts.append(f"UNTIL={_date_stamp(item['recurrence_until'])}")
    if item.get("recurrence_count"):
        parts.append(f"COUNT={item['recurrence_count']}")
    return "RRULE:" + ";".join(parts)


def _fold(line: str) -> list[str]:
    """RFC 5545 75-octet line folding (approximate, char-based is fine for UTF-8 clients)."""
    if len(line) <= 74:
        return [line]
    out = []
    while len(line) > 74:
        out.append(line[:74])
        line = " " + line[74:]
    out.append(line)
    return out


def _item_event(item: dict) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{item['id']}@personal-affairs",
        f"DTSTAMP:{_utc_stamp(item['updated_at'])}",
        f"SEQUENCE:{item['version']}",
        f"SUMMARY:{_escape(item['title'])}",
    ]
    if item["all_day"]:
        start = item.get("start_date") or item.get("due_date")
        end = item.get("due_date") or item.get("start_date")
        if start:
            lines.append(f"DTSTART;VALUE=DATE:{_date_stamp(start)}")
            lines.append(f"DTEND;VALUE=DATE:{_date_stamp((end or start) + timedelta(days=1))}")  # DTEND exclusive
    else:
        start = item.get("start_at") or item.get("due_at")
        end = item.get("due_at")
        if start:
            lines.append(f"DTSTART:{_utc_stamp(start)}")
            if end and end > start:
                lines.append(f"DTEND:{_utc_stamp(end)}")
            else:
                minutes = item.get("estimated_minutes") or 60
                lines.append(f"DTEND:{_utc_stamp(start + timedelta(minutes=minutes))}")
    if item["status"] == "done":
        lines.append("STATUS:COMPLETED")
    rule = _rrule(item)
    if rule:
        lines.append(rule)
    if item.get("notes"):
        lines.append(f"DESCRIPTION:{_escape(item['notes'])}")
    lines.append("END:VEVENT")
    return lines


def build_feed(conn: Connection, user_id: UUID) -> str:
    items = list(
        conn.execute(
            """
            SELECT id, title, notes, status, priority, all_day,
                   start_at, due_at, start_date, due_date,
                   recurrence_freq, recurrence_interval, recurrence_until, recurrence_count,
                   estimated_minutes, version, updated_at
            FROM personal_affairs.items
            WHERE user_id = %s AND archived_at IS NULL AND deleted_at IS NULL
              AND status <> 'cancelled'
              AND COALESCE(start_at, due_at, start_date, due_date) IS NOT NULL
            ORDER BY COALESCE(start_at, due_at) NULLS LAST
            """,
            (user_id,),
        ).fetchall()
    )
    milestones = list(
        conn.execute(
            """
            SELECT m.id, m.title, m.due_date, m.status, m.updated_at
            FROM personal_affairs.milestones m
            JOIN personal_affairs.projects p ON p.id = m.project_id
            WHERE m.user_id = %s AND m.due_date IS NOT NULL AND m.status <> 'cancelled'
              AND p.archived_at IS NULL
            """,
            (user_id,),
        ).fetchall()
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "REFRESH-INTERVAL;VALUE=DURATION:PT15M",
        "X-PUBLISHED-TTL:PT15M",
        "X-WR-CALNAME:个人事务",
    ]
    for item in items:
        lines.extend(_item_event(item))
    for milestone in milestones:
        status_line = "STATUS:COMPLETED" if milestone["status"] == "done" else "STATUS:CONFIRMED"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:milestone-{milestone['id']}@personal-affairs",
                f"DTSTAMP:{_utc_stamp(milestone['updated_at'])}",
                "SEQUENCE:0",
                f"SUMMARY:◆ {_escape(milestone['title'])}",
                f"DTSTART;VALUE=DATE:{_date_stamp(milestone['due_date'])}",
                f"DTEND;VALUE=DATE:{_date_stamp(milestone['due_date'] + timedelta(days=1))}",
                status_line,
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")

    folded: list[str] = []
    for line in lines:
        folded.extend(_fold(line))
    return "\r\n".join(folded) + "\r\n"


def user_for_token(conn: Connection, token: str) -> dict | None:
    row: Any = conn.execute(
        "SELECT user_id FROM personal_affairs.user_preferences WHERE ics_token = %s",
        (token,),
    ).fetchone()
    return row
