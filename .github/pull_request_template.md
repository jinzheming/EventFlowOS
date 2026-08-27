## Summary

-

## Verification

- [ ] Backend tests: `uv run pytest -q`
- [ ] Backend lint/type checks: `uv run ruff check src tests` and `uv run pyright`
- [ ] Frontend checks: `npm run lint --prefix frontend` and `npm run build --prefix frontend`
- [ ] Compose validation: dev and server compose configs render successfully
- [ ] Dependency or security-sensitive changes include relevant audit output

## Safety Checklist

- [ ] No real `.env` files, credentials, tokens, private keys, session cookies, personal exports, or private hostnames are included
- [ ] Runtime configuration changes are documented in `infra/.env.example` and deployment docs
- [ ] Database migrations are forward-only and have a rollback/restore note
- [ ] Auth, CSRF, webhook, outbound HTTP, and deployment changes preserve conservative defaults
- [ ] User-facing behavior changes are reflected in README or docs when needed
