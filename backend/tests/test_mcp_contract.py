"""P9a contract tests: PAT mechanics and the MCP tool surface.

No database is required — these exercise pure helpers and the FastMCP tool
registration only.
"""
import asyncio

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
    }
    assert expected <= names
