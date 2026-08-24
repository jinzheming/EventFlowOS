"""P9a contract tests: PAT mechanics and the MCP tool surface.

No database is required — these exercise pure helpers and the FastMCP tool
registration only.
"""
import asyncio
from typing import Any
from uuid import uuid4

import pytest

from personal_affairs.domain.errors import DomainError, ErrorCode
from personal_affairs.storage.repositories.tokens import PAT_PREFIX, generate_pat
from personal_affairs.storage.repositories.users import hash_token


def test_pat_format_and_hash_roundtrip() -> None:
    token = generate_pat()
    assert token.startswith(PAT_PREFIX)
    assert len(token) > len(PAT_PREFIX) + 20
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != hash_token("pa_some_other_token")


def test_require_csrf_skips_pat_with_write_scope() -> None:
    from personal_affairs.api.dependencies import require_csrf

    require_csrf(x_csrf_token=None, session={"auth_method": "pat", "pat_scopes": ["read", "write"]})


def test_require_csrf_rejects_readonly_pat() -> None:
    from personal_affairs.api.dependencies import require_csrf

    with pytest.raises(DomainError) as exc:
        require_csrf(x_csrf_token=None, session={"auth_method": "pat", "pat_scopes": ["read"]})
    assert exc.value.code == ErrorCode.PAT_SCOPE_FORBIDDEN


def test_require_csrf_still_requires_header_for_cookie() -> None:
    from personal_affairs.api.dependencies import require_csrf

    with pytest.raises(DomainError) as exc:
        require_csrf(x_csrf_token=None, session={"auth_method": "cookie", "csrf_token": "abc"})
    assert exc.value.code == ErrorCode.CSRF_REQUIRED


def test_mcp_tool_surface() -> None:
    from personal_affairs.mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        "pa_list_items",
        "pa_get_item",
        "pa_create_item",
        "pa_update_item",
        "pa_complete_item",
        "pa_list_people",
        "pa_create_person",
        "pa_update_person",
        "pa_set_reminder",
        "pa_get_reminder",
        "pa_delete_reminder",
        "pa_list_deliveries",
        "pa_ack_delivery",
        "pa_snooze_delivery",
        "pa_retry_delivery",
        "pa_get_channels",
        "pa_reminder_health",
        "pa_list_calendar",
        "pa_create_calendar_event",
        "pa_propose_item",
        "pa_approve_proposal",
        "pa_reject_proposal",
        "pa_parse_meeting_invite",
        "pa_get_executive_briefing",
        "pa_find_free_slots",
    }
    assert expected <= names


def test_mcp_parse_meeting_invite_contract() -> None:
    from personal_affairs.mcp.server import pa_parse_meeting_invite

    parsed = asyncio.run(
        pa_parse_meeting_invite(
            "会议主题：项目例会\n会议时间：2026-08-24 10:00-10:30\n会议号：987-654-321\n密码：abcd",
            "Asia/Shanghai",
        )
    )

    assert parsed["title"] == "项目例会"
    assert parsed["meeting_id"] == "987654321"
    assert parsed["proposed_item"]["scope"] == "work"


def test_mcp_proposal_write_contracts(monkeypatch) -> None:
    from personal_affairs.mcp import server

    user_id = uuid4()
    proposal_id = uuid4()
    calls: list[tuple[str, Any]] = []

    async def fake_authed(fn):
        return fn(object(), user_id)

    class FakeService:
        def propose(self, uid, request):
            calls.append(("propose", request))
            assert uid == user_id
            return {"id": proposal_id, "state": "pending", "proposed_payload": request.proposed_payload}

        def approve(self, uid, pid, request):
            calls.append(("approve", request))
            assert uid == user_id
            assert pid == proposal_id
            return {"id": pid, "state": "edited_approved"}, {"id": uuid4(), "title": request.edited_payload["title"]}

        def reject(self, uid, pid, state, decision_note):
            calls.append(("reject", (state, decision_note)))
            assert uid == user_id
            assert pid == proposal_id
            return {"id": pid, "state": state.value, "decision_note": decision_note}

    monkeypatch.setattr(server, "_authed", fake_authed)
    monkeypatch.setattr(server, "_proposal_service", lambda conn: FakeService())

    proposed = asyncio.run(
        server.pa_propose_item(
            '{"title":"整理会议","scope":"work"}',
            source_type="agent",
            evidence_json='{"parser":"manual"}',
            reason="unit",
        )
    )
    approved = asyncio.run(
        server.pa_approve_proposal(str(proposal_id), edited_payload_json='{"title":"改后确认","scope":"work"}')
    )
    rejected = asyncio.run(server.pa_reject_proposal(str(proposal_id), decision_note="not needed"))

    assert proposed["state"] == "pending"
    assert approved["proposal"]["state"] == "edited_approved"
    assert rejected is not None and rejected["state"] == "rejected"
    assert [name for name, _ in calls] == ["propose", "approve", "reject"]
