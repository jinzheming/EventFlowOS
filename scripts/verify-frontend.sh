#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export npm_config_cache="${npm_config_cache:-${NPM_CONFIG_CACHE:-${TMPDIR:-/tmp}/eventflowos-npm-cache}}"
export NPM_CONFIG_CACHE="$npm_config_cache"

npm ci --prefix "$ROOT/frontend"
npm audit --prefix "$ROOT/frontend" --audit-level=moderate
npm run lint --prefix "$ROOT/frontend"
npm test --prefix "$ROOT/frontend"
npm run build --prefix "$ROOT/frontend"

if [ "${RUN_E2E:-0}" = "1" ]; then
  npx --prefix "$ROOT/frontend" playwright install chromium
  npm run e2e --prefix "$ROOT/frontend"
fi
