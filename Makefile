.PHONY: verify verify-backend verify-frontend verify-compose verify-secrets verify-release

verify:
	./scripts/verify.sh

verify-backend:
	./scripts/verify-backend.sh

verify-frontend:
	./scripts/verify-frontend.sh

verify-compose:
	./scripts/verify-compose.sh

verify-secrets:
	./scripts/verify-secrets.sh

verify-release:
	./scripts/verify-release.sh
