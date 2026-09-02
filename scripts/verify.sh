#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT/scripts/verify-backend.sh"
"$ROOT/scripts/verify-frontend.sh"
"$ROOT/scripts/verify-compose.sh"
"$ROOT/scripts/verify-secrets.sh"
git -C "$ROOT" diff --check
echo "EventFlowOS verification passed."
