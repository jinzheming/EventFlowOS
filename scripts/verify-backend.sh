#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/eventflowos-uv-cache}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-${TMPDIR:-/tmp}/eventflowos-uv-tools}"
REQ_FILE="${TMPDIR:-/tmp}/eventflowos-requirements.txt"
AUDIT_FILE="${TMPDIR:-/tmp}/eventflowos-requirements-audit.txt"

cd "$ROOT/backend"
uv sync --all-extras --locked
uv export --all-extras --format requirements-txt --no-hashes --output-file "$REQ_FILE"
grep -v '^-e .' "$REQ_FILE" > "$AUDIT_FILE"
uvx pip-audit -r "$AUDIT_FILE" --no-deps --disable-pip --progress-spinner off --timeout 60
uv run pytest -q
uv run ruff check src tests
uv run pyright
