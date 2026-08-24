import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from personal_affairs.config import Settings

TMeetRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class TMeetLookupResult:
    status: str
    details: dict[str, Any] | None = None
    error_category: str | None = None
    elapsed_ms: int | None = None

    @property
    def audit(self) -> dict[str, Any]:
        value: dict[str, Any] = {"status": self.status}
        if self.error_category:
            value["error_category"] = self.error_category
        if self.elapsed_ms is not None:
            value["elapsed_ms"] = self.elapsed_ms
        return value


def lookup_tencent_meeting(
    cfg: Settings,
    *,
    meeting_id: str | None = None,
    runner: TMeetRunner = subprocess.run,
) -> TMeetLookupResult:
    if not cfg.tmeet_enabled:
        return TMeetLookupResult(status="disabled")
    if "meeting:get" not in _allowed_commands(cfg.tmeet_allowed_commands):
        return TMeetLookupResult(status="not_allowed", error_category="command_not_allowed")
    if not meeting_id:
        return TMeetLookupResult(status="skipped", error_category="missing_meeting_id")
    command = [cfg.tmeet_bin, "meeting", "get", "--meeting-id", meeting_id, "--format", "json"]
    env = _tmeet_env(cfg)
    start = perf_counter()
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=cfg.tmeet_timeout_seconds,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return TMeetLookupResult(status="timeout", error_category="timeout", elapsed_ms=_elapsed_ms(start))
    except OSError:
        return TMeetLookupResult(status="failed", error_category="cli_unavailable", elapsed_ms=_elapsed_ms(start))
    if completed.returncode != 0:
        return TMeetLookupResult(status="failed", error_category="cli_exit", elapsed_ms=_elapsed_ms(start))
    try:
        decoded = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return TMeetLookupResult(status="failed", error_category="invalid_json", elapsed_ms=_elapsed_ms(start))
    if not isinstance(decoded, dict):
        return TMeetLookupResult(status="failed", error_category="invalid_shape", elapsed_ms=_elapsed_ms(start))
    details = _unwrap_details(decoded)
    return TMeetLookupResult(status="success", details=details, elapsed_ms=_elapsed_ms(start))


def _allowed_commands(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def _tmeet_env(cfg: Settings) -> dict[str, str] | None:
    if not cfg.tmeet_home:
        return None
    env = os.environ.copy()
    env["TMEET_HOME"] = cfg.tmeet_home
    return env


def _unwrap_details(decoded: dict[str, Any]) -> dict[str, Any]:
    for key in ("data", "meeting", "result"):
        value = decoded.get(key)
        if isinstance(value, dict):
            return value
    return decoded


def _elapsed_ms(start: float) -> int:
    return max(0, int((perf_counter() - start) * 1000))
