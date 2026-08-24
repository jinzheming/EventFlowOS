import json
import subprocess

from personal_affairs.application.tmeet_adapter import lookup_tencent_meeting
from personal_affairs.config import Settings


def test_tmeet_lookup_is_disabled_by_default() -> None:
    called = False

    def runner(*args, **kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess(args[0], 0, stdout="{}", stderr="")

    result = lookup_tencent_meeting(Settings(), meeting_id="987654321", runner=runner)

    assert result.status == "disabled"
    assert called is False


def test_tmeet_lookup_runs_only_allowed_read_command() -> None:
    observed: dict = {}

    def runner(command, **kwargs):
        observed["command"] = command
        observed["timeout"] = kwargs["timeout"]
        observed["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"data": {"subject": "产品例会"}}),
            stderr="",
        )

    result = lookup_tencent_meeting(
        Settings(tmeet_enabled=True, tmeet_bin="/usr/local/bin/tmeet", tmeet_home="/runtime/tmeet"),
        meeting_id="987654321",
        runner=runner,
    )

    assert result.status == "success"
    assert result.details == {"subject": "产品例会"}
    assert observed["command"] == [
        "/usr/local/bin/tmeet",
        "meeting",
        "get",
        "--meeting-id",
        "987654321",
        "--format",
        "json",
    ]
    assert observed["timeout"] == 8.0
    assert observed["env"]["TMEET_HOME"] == "/runtime/tmeet"


def test_tmeet_lookup_refuses_when_command_not_whitelisted() -> None:
    result = lookup_tencent_meeting(
        Settings(tmeet_enabled=True, tmeet_allowed_commands=""),
        meeting_id="987654321",
    )

    assert result.status == "not_allowed"
    assert result.audit == {"status": "not_allowed", "error_category": "command_not_allowed"}
