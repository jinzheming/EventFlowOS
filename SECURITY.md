# Security Policy

## Supported Versions

EventFlowOS is an early-preview project. Security fixes target the latest `main` branch only unless a maintainer explicitly documents a release branch.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the repository owner, preferably through GitHub private vulnerability reporting when it is enabled for the repository. Do not open a public issue with exploit details, live credentials, session cookies, personal access tokens, database URLs, webhook secrets, private keys, or production hostnames.

Include enough detail to reproduce the issue safely:

- affected endpoint, feature, or file path;
- expected and observed behavior;
- minimal reproduction steps against a local or test deployment;
- impact assessment and any known workaround.

## Deployment Security Notes

- Keep real runtime secrets outside git and start from `infra/.env.example` only as a template.
- Rotate all credentials before making a previously private deployment public.
- Keep `PERSONAL_AFFAIRS_API_DOCS_ENABLED=false` in production unless docs are protected elsewhere.
- Set `PERSONAL_AFFAIRS_ALLOWED_HOSTS` for production Host header validation.
- Keep private webhook destinations disabled unless the deployment intentionally needs trusted internal callbacks.
- Add edge rate limits for login, personal access token creation, webhook creation, and other expensive endpoints.

## Secret Scanning

Before opening the repository, run a full-history secret scan where possible:

```bash
gitleaks detect --source . --no-git=false
```

If a real secret is found in current files or history, rotate it first. If the repository history contains live secrets, rewrite history only after explicit maintainer approval and after coordinating with anyone who has cloned the repository.
