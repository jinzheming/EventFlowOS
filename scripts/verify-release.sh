#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

: "${PERSONAL_AFFAIRS_TEST_DATABASE_URL:?Set PERSONAL_AFFAIRS_TEST_DATABASE_URL to run release PostgreSQL integration tests.}"
RUN_E2E=1 VERIFY_REQUIRE_GITLEAKS=1 "$ROOT/scripts/verify.sh"

echo "Release gate passed. Record this command output in the release notes."
