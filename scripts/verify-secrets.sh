#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source "$ROOT" --no-git=false
  exit 0
fi

if [ "${VERIFY_REQUIRE_GITLEAKS:-0}" = "1" ]; then
  echo "gitleaks is required for release verification but was not found." >&2
  exit 1
fi

echo "gitleaks not found; running fallback current-file secret pattern scan." >&2
if rg -n --hidden --glob '!.git/**' --glob '!backend/.venv/**' --glob '!frontend/node_modules/**' --glob '!frontend/dist/**' -S '(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]+|BEGIN (RSA|OPENSSH|PRIVATE) KEY|pa_[A-Za-z0-9_-]{32,})' "$ROOT"; then
  echo "Potential secret-like value found by fallback scan." >&2
  exit 1
fi
