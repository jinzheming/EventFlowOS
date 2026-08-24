"""P9a: MCP server for Personal Affairs.

Same-process FastMCP server exposing the core item / people / reminder surface
to AI agents. Every tool call authenticates a personal access token
(PERSONAL_AFFAIRS_MCP_TOKEN for stdio, Authorization: Bearer for
streamable HTTP) and runs against the shared PostgreSQL pool through the same
repositories/services as the REST API — single source of truth.

Note: no ``from __future__ import annotations`` here — FastMCP introspects
runtime annotations and stringified ones break it.
"""
import asyncio
import json
import os
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from personal_affairs.api.schemas import ItemCreate, ItemPatch, ReminderPut
from personal_affairs.application.calendar_query_service import CalendarQueryService
from personal_affairs.application.item_service import ItemService
from personal_affairs.application.people_service import PeopleService
from personal_affairs.application.reminder_service import ReminderService
from personal_affairs.config import get_settings
from personal_affairs.domain.enums import ItemScope, ItemStatus, ReminderTiming
from personal_affairs.storage.database import connection
from personal_affairs.storage.repositories.activity import ActivityRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.people import PeopleRepository
from personal_affairs.storage.repositories.projects import ProjectsRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository
from personal_affairs.storage.repositories.tokens import TokensRepository

_MCP_HOST = os.environ.get("PERSONAL_AFFAIRS_MCP_HOST", "127.0.0.1")
_MCP_PORT = int(os.environ.get("PERSONAL_AFFAIRS_MCP_PORT", "18099"))

mcp = FastMCP("Personal Affairs", host=_MCP_HOST, port=_MCP_PORT)


def _pat() -> str:
    token = os.environ.get("PERSONAL_AFFAIRS_MCP_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "PERSONAL_AFFAIRS_MCP_TOKEN is not set; create a personal access token "
            "via POST /api/v1/auth/tokens and export it"
        )
    return token


async def _user_id() -> UUID:
    def _resolve() -> UUID:
        with connection() as conn:
            row = TokensRepository(conn).get_by_token(_pat())
            if not row:
                raise RuntimeError("invalid or expired personal access token")
            return row["user_id"]

    return await asyncio.to_thread(_resolve)


async def _authed(fn) -> Any:
    """Run a sync DB callback receiving (conn, user_id) off the event loop."""
    user_id = await _user_id()

    def _run() -> Any:
        with connection() as conn:
            return fn(conn, user_id)

    return await asyncio.to_thread(_run)


def _parse_if_match(if_match: str | None) -> int:
    if not if_match:
        raise ValueError("if_match is required (item version, e.g. '3' or 'v3')")
    cleaned = if_match.strip().strip('"')
    if cleaned.startswith("v"):
        cleaned = cleaned[1:]
    return int(cleaned)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


# ---------------------------------------------------------------- items

@mcp.tool()
async def pa_list_items(
    scope: str | None = None,
    status: str | None = None,
    project_id: str | None = None,
    include_archived: bool = False,
    deleted: bool = False,
    search: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List personal affairs items, optionally filtered by scope/status/project/text."""
    return await _authed(
        lambda conn, uid: ItemsRepository(conn).list_items(
            uid,
            ItemScope(scope) if scope else None,
            include_archived,
            UUID(project_id) if project_id else None,
            ItemStatus(status) if status else None,
            limit,
            search,
            deleted,
        )
    )


@mcp.tool()
async def pa_get_item(item_id: str) -> dict | None:
    """Get a single item by id (includes tags, people, project name)."""
    return await _authed(lambda conn, uid: ItemsRepository(conn).get_item(uid, UUID(item_id)))


@mcp.tool()
async def pa_create_item(
    title: str,
    scope: str,
    notes: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    project_id: str | None = None,
    all_day: bool = True,
    start_at: str | None = None,
    due_at: str | None = None,
    start_date: str | None = None,
    due_date: str | None = None,
    waiting_on: str | None = None,
    waiting_follow_up_date: str | None = None,
    recurrence_freq: str | None = None,
    recurrence_interval: int | None = None,
    recurrence_until: str | None = None,
    recurrence_count: int | None = None,
    estimated_minutes: int | None = None,
    tag_ids: list[str] | None = None,
    people: list[dict] | None = None,
    client_request_id: str | None = None,
) -> dict:
    """Create an item (idempotent via client_request_id). scope: work|personal."""
    fields = {
        "title": title,
        "scope": ItemScope(scope),
        "status": ItemStatus(status) if status else None,
        "priority": priority,
        "project_id": UUID(project_id) if project_id else None,
        "all_day": all_day,
        "start_at": _parse_datetime(start_at),
        "due_at": _parse_datetime(due_at),
        "start_date": date.fromisoformat(start_date) if start_date else None,
        "due_date": date.fromisoformat(due_date) if due_date else None,
        "waiting_on": waiting_on,
        "waiting_follow_up_date": date.fromisoformat(waiting_follow_up_date) if waiting_follow_up_date else None,
        "recurrence_freq": recurrence_freq,
        "recurrence_interval": recurrence_interval,
        "recurrence_until": date.fromisoformat(recurrence_until) if recurrence_until else None,
        "recurrence_count": recurrence_count,
        "estimated_minutes": estimated_minutes,
        "tag_ids": [UUID(t) for t in tag_ids] if tag_ids else None,
        "people": people,
        "client_request_id": client_request_id,
    }
    request = ItemCreate(**{k: v for k, v in fields.items() if v is not None})
    item, _created = await _authed(
        lambda conn, uid: ItemService(ItemsRepository(conn), ActivityRepository(conn)).create(uid, request)
    )
    return item


@mcp.tool()
async def pa_update_item(
    item_id: str,
    if_match: str,
    title: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    project_id: str | None = None,
    all_day: bool | None = None,
    start_at: str | None = None,
    due_at: str | None = None,
    start_date: str | None = None,
    due_date: str | None = None,
    waiting_on: str | None = None,
    waiting_follow_up_date: str | None = None,
    recurrence_freq: str | None = None,
    recurrence_interval: int | None = None,
    recurrence_until: str | None = None,
    recurrence_count: int | None = None,
    estimated_minutes: int | None = None,
    tag_ids: list[str] | None = None,
    people: list[dict] | None = None,
) -> dict | None:
    """Update an item. Pass if_match = current item version (e.g. 'v3')."""
    item_id_uuid = UUID(item_id)
    version = _parse_if_match(if_match)
    patch_fields = {
        "title": title,
        "notes": notes,
        "status": ItemStatus(status) if status else None,
        "priority": priority,
        "project_id": UUID(project_id) if project_id else None,
        "all_day": all_day,
        "start_at": _parse_datetime(start_at),
        "due_at": _parse_datetime(due_at),
        "start_date": date.fromisoformat(start_date) if start_date else None,
        "due_date": date.fromisoformat(due_date) if due_date else None,
        "waiting_on": waiting_on,
        "waiting_follow_up_date": date.fromisoformat(waiting_follow_up_date) if waiting_follow_up_date else None,
        "recurrence_freq": recurrence_freq,
        "recurrence_interval": recurrence_interval,
        "recurrence_until": date.fromisoformat(recurrence_until) if recurrence_until else None,
        "recurrence_count": recurrence_count,
        "estimated_minutes": estimated_minutes,
        "tag_ids": [UUID(t) for t in tag_ids] if tag_ids else None,
        "people": people,
    }
    request = ItemPatch(**{k: v for k, v in patch_fields.items() if v is not None})

    def _run(conn, uid):
        repo = ItemsRepository(conn)
        current = repo.get_item(uid, item_id_uuid)
        if not current:
            return None
        return ItemService(repo, ActivityRepository(conn)).patch(uid, item_id_uuid, current, version, request)

    return await _authed(_run)


@mcp.tool()
async def pa_complete_item(item_id: str, if_match: str) -> dict | None:
    """Complete an item (moves to done, materializes the next recurring occurrence)."""
    item_id_uuid = UUID(item_id)
    version = _parse_if_match(if_match)

    def _run(conn, uid):
        repo = ItemsRepository(conn)
        current = repo.get_item(uid, item_id_uuid)
        if not current:
            return None
        return ItemService(repo, ActivityRepository(conn)).patch(
            uid, item_id_uuid, current, version, ItemPatch(status=ItemStatus.DONE)
        )

    return await _authed(_run)


# ---------------------------------------------------------------- people

@mcp.tool()
async def pa_list_people(include_inactive: bool = True) -> list[dict]:
    """List the people directory."""
    return await _authed(lambda conn, uid: PeopleRepository(conn).list_people(uid, include_inactive))


@mcp.tool()
async def pa_create_person(name: str, identity: str | None = None, note: str | None = None) -> dict:
    """Create a person in the directory."""
    return await _authed(lambda conn, uid: PeopleService(PeopleRepository(conn)).create(uid, name, identity, note))


@mcp.tool()
async def pa_update_person(
    person_id: str,
    name: str | None = None,
    identity: str | None = None,
    note: str | None = None,
    active: bool | None = None,
) -> dict | None:
    """Update a person (only provided fields change)."""
    patch = {k: v for k, v in {"name": name, "identity": identity, "note": note, "active": active}.items() if v is not None}
    person_id_uuid = UUID(person_id)
    return await _authed(lambda conn, uid: PeopleService(PeopleRepository(conn)).patch(uid, person_id_uuid, patch))


# ---------------------------------------------------------------- reminders

@mcp.tool()
async def pa_set_reminder(
    item_id: str,
    timing: str = "before_due",
    offset_minutes: int = 10,
    timezone: str = "Asia/Shanghai",
    external_enabled: bool = False,
) -> dict | None:
    """Set an item reminder. timing: at_start|before_start|before_due."""
    item_id_uuid = UUID(item_id)
    request = ReminderPut(
        timing=ReminderTiming(timing),
        offset_minutes=offset_minutes,
        timezone=timezone,
        external_enabled=external_enabled,
    )

    def _run(conn, uid):
        items = ItemsRepository(conn)
        if not items.get_item(uid, item_id_uuid):
            return None
        return ReminderService(RemindersRepository(conn), items, get_settings()).upsert(uid, item_id_uuid, request)

    return await _authed(_run)


@mcp.tool()
async def pa_get_reminder(item_id: str) -> dict | None:
    """Get the active reminder for an item."""
    return await _authed(lambda conn, uid: RemindersRepository(conn).get_active_for_item(uid, UUID(item_id)))


@mcp.tool()
async def pa_delete_reminder(item_id: str) -> None:
    """Cancel the item's reminder."""
    await _authed(lambda conn, uid: RemindersRepository(conn).deactivate_for_item(uid, UUID(item_id)))
    return None


@mcp.tool()
async def pa_list_deliveries(
    channel: str | None = None,
    status: str | None = None,
    unseen: bool = False,
    limit: int = 100,
) -> list[dict]:
    """List reminder deliveries; unseen=true filters to delivered, unacknowledged."""
    return await _authed(
        lambda conn, uid: RemindersRepository(conn).list_deliveries(uid, limit, channel, status, unseen)
    )


@mcp.tool()
async def pa_ack_delivery(delivery_id: str) -> dict | None:
    """Acknowledge a delivered reminder (mark as handled)."""
    return await _authed(lambda conn, uid: RemindersRepository(conn).acknowledge(uid, UUID(delivery_id)))


@mcp.tool()
async def pa_snooze_delivery(delivery_id: str, snooze_until: str) -> dict | None:
    """Snooze a delivered reminder until the given ISO datetime."""
    until = _parse_datetime(snooze_until)
    assert until is not None
    return await _authed(lambda conn, uid: RemindersRepository(conn).snooze(uid, UUID(delivery_id), until))


@mcp.tool()
async def pa_retry_delivery(delivery_id: str) -> dict | None:
    """Retry a dead delivery."""
    return await _authed(lambda conn, uid: RemindersRepository(conn).retry_dead(uid, UUID(delivery_id)))


@mcp.tool()
async def pa_get_channels() -> dict:
    """Which external notification channels are configured."""
    await _user_id()
    cfg = get_settings()
    return {"feishu_configured": bool(cfg.feishu_webhook_url), "ntfy_configured": bool(cfg.ntfy_topic_url)}


@mcp.tool()
async def pa_reminder_health() -> dict:
    """Reminder worker health: lag, pending/retry/dead counts."""
    await _user_id()

    def _run() -> dict:
        with connection() as conn:
            return RemindersRepository(conn).health()

    return await asyncio.to_thread(_run)


# ---------------------------------------------------------------- calendar

@mcp.tool()
async def pa_list_calendar(
    start: str,
    end: str,
    kinds: str | None = None,
) -> list[dict]:
    """List calendar events in a window.

    start/end: ISO datetimes (timed events) or dates (all-day); a single
    date like 2026-08-22 covers the whole day. kinds: comma-separated
    work_item|personal_item|milestone (default all).
    """
    selected = set(k for k in kinds.split(",") if k) if kinds else None

    def _run(conn, uid):
        return CalendarQueryService(ItemsRepository(conn), ProjectsRepository(conn)).events(uid, start, end, selected)

    return await _authed(_run)


@mcp.tool()
async def pa_create_calendar_event(
    title: str,
    scope: str,
    start_at: str | None = None,
    due_at: str | None = None,
    due_date: str | None = None,
    start_date: str | None = None,
    all_day: bool = False,
    notes: str | None = None,
    estimated_minutes: int | None = None,
    reminder_timing: str | None = None,
    reminder_offset_minutes: int = 10,
    client_request_id: str | None = None,
) -> dict:
    """Create a calendar event (timed or all-day work/personal item).

    Timed events: provide start_at/due_at as ISO datetimes. All-day events:
    all_day=true with due_date/start_date (ISO dates). Optionally attach a
    reminder (timing: at_start|before_start|before_due).
    """
    fields = {
        "title": title,
        "scope": ItemScope(scope),
        "all_day": all_day,
        "start_at": _parse_datetime(start_at),
        "due_at": _parse_datetime(due_at),
        "start_date": date.fromisoformat(start_date) if start_date else None,
        "due_date": date.fromisoformat(due_date) if due_date else None,
        "notes": notes,
        "estimated_minutes": estimated_minutes,
        "client_request_id": client_request_id,
    }
    request = ItemCreate(**{k: v for k, v in fields.items() if v is not None})

    def _run(conn, uid):
        items = ItemsRepository(conn)
        item, _created = ItemService(items, ActivityRepository(conn)).create(uid, request)
        if reminder_timing:
            ReminderService(RemindersRepository(conn), items, get_settings()).upsert(
                uid,
                item["id"],
                ReminderPut(
                    timing=ReminderTiming(reminder_timing),
                    offset_minutes=reminder_offset_minutes,
                    timezone="Asia/Shanghai",
                    external_enabled=False,
                ),
            )
        return item

    return await _authed(_run)


# ---------------------------------------------------------------- resources

@mcp.resource("pa://items/{item_id}")
async def item_resource(item_id: str) -> str:
    row = await _authed(lambda conn, uid: ItemsRepository(conn).get_item(uid, UUID(item_id)))
    if not row:
        return "not found"
    return json.dumps(row, ensure_ascii=False, default=str)


@mcp.resource("pa://people/{person_id}")
async def people_resource(person_id: str) -> str:
    row = await _authed(lambda conn, uid: PeopleRepository(conn).get(uid, UUID(person_id)))
    if not row:
        return "not found"
    return json.dumps(row, ensure_ascii=False, default=str)


@mcp.resource("pa://reminders/today")
async def today_reminders_resource() -> str:
    today = date.today()

    def _run(conn, uid):
        rows = RemindersRepository(conn).list_deliveries(uid, limit=500)
        return [r for r in rows if r["scheduled_for"].date() == today and r["status"] != "cancelled"]

    rows = await _authed(_run)
    return json.dumps(rows, ensure_ascii=False, default=str)


# ---------------------------------------------------------------- prompts

@mcp.prompt()
def pa_daily_brief() -> str:
    return (
        "You are the user's personal affairs assistant. Build a concise daily brief: "
        "query pa_list_deliveries(unseen=True) for pending reminders, pa_list_items for "
        "today's work/personal items, then propose a prioritized action plan. "
        "Prefer Chinese output."
    )


def main() -> None:
    transport = os.environ.get("PERSONAL_AFFAIRS_MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
