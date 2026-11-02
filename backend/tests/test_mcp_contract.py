"""P9a contract tests: PAT mechanics and the MCP tool surface.

No database is required — these exercise pure helpers and the FastMCP tool
registration only.
"""
import ast
import asyncio
import inspect
import textwrap
from typing import Any
from uuid import uuid4

import pytest

from personal_affairs.domain.errors import DomainError, ErrorCode
from personal_affairs.storage.repositories.tokens import PAT_PREFIX, generate_pat
from personal_affairs.storage.repositories.users import hash_token

# Every tool exposed over MCP, classified by the scope it demands. This table is
# the source of truth: adding or removing a tool without updating it fails
# ``test_mcp_tool_surface_is_fully_classified``, and every entry is checked
# against the ``require_write=`` literal actually passed to ``_authed`` /
# ``_user_id``. A write tool that forgets the flag (the read-only-PAT bypass
# fixed in 2026-11) therefore fails the suite instead of shipping.
WRITE_TOOLS = frozenset(
    {
        "pa_ack_delivery",
        "pa_approve_proposal",
        "pa_complete_item",
        "pa_create_calendar_event",
        "pa_create_item",
        "pa_create_person",
        "pa_delete_reminder",
        "pa_propose_item",
        "pa_reject_proposal",
        "pa_retry_delivery",
        "pa_set_item_relations",
        "pa_set_reminder",
        "pa_snooze_delivery",
        "pa_update_item",
        "pa_update_person",
    }
)
READ_TOOLS = frozenset(
    {
        "pa_assess_schedule_feasibility",
        "pa_find_free_slots",
        "pa_get_channels",
        "pa_get_executive_briefing",
        "pa_get_item",
        "pa_get_project_context",
        "pa_get_reminder",
        "pa_list_calendar",
        "pa_list_deliveries",
        "pa_list_items",
        "pa_list_people",
        "pa_parse_meeting_input",
        "pa_reminder_health",
        "pa_resolve_offline_location",
    }
)
# Pure functions: no token, no database.
PURE_TOOLS = frozenset({"pa_parse_meeting_invite"})


def _declared_require_write(fn) -> bool | None:
    """Return the literal ``require_write=`` flag a tool passes to the auth helpers.

    ``None`` means the tool never authenticates.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if callee not in {"_authed", "_user_id"}:
            continue
        for keyword in node.keywords:
            if keyword.arg == "require_write" and isinstance(keyword.value, ast.Constant):
                return bool(keyword.value.value)
    return None


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


def test_mcp_tool_surface_is_fully_classified() -> None:
    from personal_affairs.mcp.server import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    classified = WRITE_TOOLS | READ_TOOLS | PURE_TOOLS

    assert classified - names == set(), "classified tools missing from the server"
    assert names - classified == set(), "unclassified tools on the server"
    assert WRITE_TOOLS.isdisjoint(READ_TOOLS | PURE_TOOLS)
    assert len(WRITE_TOOLS) == 15
    assert len(READ_TOOLS) == 14


@pytest.mark.parametrize("name", sorted(WRITE_TOOLS | READ_TOOLS))
def test_mcp_tool_declares_expected_scope(name: str) -> None:
    """Write tools must demand the write scope; read tools must not."""
    from personal_affairs.mcp import server

    assert _declared_require_write(getattr(server, name)) is (name in WRITE_TOOLS)


def test_mcp_pure_tool_never_authenticates() -> None:
    from personal_affairs.mcp import server

    assert _declared_require_write(server.pa_parse_meeting_invite) is None


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


def test_mcp_create_item_forwards_notes_and_agent_identity(monkeypatch) -> None:
    """Regression: pa_create_item silently dropped ``notes`` before the service."""
    from personal_affairs.mcp import server

    captured: dict[str, Any] = {}

    class FakeItemService:
        def __init__(self, repo, activity) -> None:
            pass

        def create(self, uid, request, *, created_by_actor, source_context):
            captured["request"] = request
            captured["actor"] = created_by_actor
            captured["source"] = source_context
            return {"id": str(uuid4()), "title": request.title}, True

    async def fake_authed(fn, *, require_write):
        assert require_write is True
        return fn(object(), uuid4())

    monkeypatch.setattr(server, "_authed", fake_authed)
    monkeypatch.setattr(server, "ItemService", FakeItemService)
    monkeypatch.setattr(server, "ItemsRepository", lambda conn: None)
    monkeypatch.setattr(server, "ActivityRepository", lambda conn: None)

    asyncio.run(server.pa_create_item("整理会议纪要", "work", notes="重点：三个待办", all_day=False))

    assert captured["request"].notes == "重点：三个待办"
    assert captured["request"].all_day is False
    assert captured["actor"] == "agent"
    assert captured["source"]["surface"] == "mcp"


def test_mcp_proposal_write_contracts(monkeypatch) -> None:
    from personal_affairs.mcp import server

    user_id = uuid4()
    proposal_id = uuid4()
    calls: list[tuple[str, Any]] = []

    required_write_scopes: list[bool] = []

    async def fake_authed(fn, *, require_write):
        required_write_scopes.append(require_write)
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
    assert required_write_scopes == [True, True, True]


def test_mcp_pat_write_scope_enforced(monkeypatch) -> None:
    from contextlib import nullcontext

    from personal_affairs.mcp import server

    user_id = uuid4()
    token_row = {
        "user_id": user_id,
        "token_name": "test-agent",
        "scopes": ["read"],
    }

    class FakeTokensRepository:
        def __init__(self, conn):
            pass

        def get_by_token(self, token):
            assert token == "pa_test"
            return token_row

    monkeypatch.setattr(server, "_pat", lambda: "pa_test")
    monkeypatch.setattr(server, "connection", lambda: nullcontext(object()))
    monkeypatch.setattr(server, "TokensRepository", FakeTokensRepository)

    assert asyncio.run(server._user_id(require_write=False)) == user_id
    with pytest.raises(DomainError) as exc:
        asyncio.run(server._user_id(require_write=True))
    assert exc.value.code == ErrorCode.PAT_SCOPE_FORBIDDEN

    token_row["scopes"] = ["read", "write"]

    async def _accepted() -> tuple:
        user = await server._user_id(require_write=True)
        return user, server._agent_source()

    user, source = asyncio.run(_accepted())
    assert user == user_id
    # The token name, not just the surface, must reach the audit trail.
    assert source == {"surface": "mcp", "agent_token": "test-agent"}
