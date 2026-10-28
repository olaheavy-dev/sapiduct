# Owned by house-template-nextjs. Included by the base Makefile; adds the frontend's install and
# checks to `make install`, `make check` and `make check-fast`. Its own targets end in -frontend,
# so they never clash with another layer's (the FastAPI layer has `dev`, `test` and `lock`).

FRONTEND := pnpm --dir frontend
# The end-to-end tests' browser: Chromium in Playwright's Linux image (needs Docker), which also
# compares the screenshots, when E2E_DOCKER is set (CI sets it); otherwise Chromium installed here.
E2E_DOCKER ?= $(CI)
E2E := $(FRONTEND) $(if $(E2E_DOCKER),e2e:docker,e2e)

INSTALLS += install-nextjs
CHECKS += check-nextjs check-api-types
FAST_CHECKS += check-fast-nextjs

.PHONY: install-nextjs check-nextjs check-fast-nextjs lock-frontend dev-frontend test-frontend build-frontend e2e-frontend screenshots-frontend image-frontend up-frontend api-types check-api-types

install-nextjs: ## Install the frontend's dependencies (from frontend/pnpm-lock.yaml; needs Node 26 and pnpm 12) and, without E2E_DOCKER, Playwright's Chromium
	$(FRONTEND) install --frozen-lockfile
	$(if $(E2E_DOCKER),,$(FRONTEND) exec playwright install --only-shell chromium)

check-nextjs: ## Frontend: peer dependencies, lint, format, types, unit tests, a production build and the end-to-end tests against it
	# Fails when an update leaves a package outside its peers' ranges (the OpenTelemetry set moves together).
	$(FRONTEND) peers check
	$(FRONTEND) lint
	$(FRONTEND) format:check
	$(FRONTEND) typecheck
	$(FRONTEND) test
	$(FRONTEND) build
	$(E2E)

check-fast-nextjs: ## Frontend: lint and types (the pre-push and stop-hook checks)
	$(FRONTEND) lint
	$(FRONTEND) typecheck

lock-frontend: ## Update frontend/pnpm-lock.yaml after changing frontend/package.json
	$(FRONTEND) install --lockfile-only

dev-frontend: ## Run the frontend with reload on http://localhost:3000
	$(FRONTEND) dev

test-frontend: ## Run the frontend's unit tests
	$(FRONTEND) test

build-frontend: ## Build the frontend for production (the standalone server)
	$(FRONTEND) build

e2e-frontend: build-frontend ## Run the end-to-end tests (Playwright, axe) against a fresh production build; E2E_DOCKER=1 adds the screenshots
	$(E2E)

image-frontend: ## Build the web image from frontend/Dockerfile
	docker compose build web

up-frontend: ## Run the frontend from its image on http://127.0.0.1:3000, with the backend's services
	docker compose up -d --build --wait web

screenshots-frontend: build-frontend ## Remake the screenshots that changed (frontend/e2e/screenshots/) in Playwright's Linux image, then review and commit them
	$(FRONTEND) e2e:docker --update-snapshots=changed

API_TYPES := src/lib/api/schema.d.ts
# The backend's OpenAPI schema, from its code: no server, database or keys needed.
OPENAPI_EXPORT := uv --directory backend run --frozen python -c 'import json, sys; from app.main import create_app; from app.settings import Settings; json.dump(create_app(Settings(_env_file=None, app_env="test")).openapi(), sys.stdout)'

api-types: ## Regenerate the frontend's API types (frontend/src/lib/api/schema.d.ts) from the FastAPI backend
	@schema=$$(mktemp); trap 'rm -f "$$schema"' EXIT; \
	$(OPENAPI_EXPORT) > "$$schema" && $(FRONTEND) exec openapi-typescript "$$schema" -o $(API_TYPES)

check-api-types: ## Fail when the frontend's API types are behind the backend (run make api-types)
	@schema=$$(mktemp); types=$$(mktemp -d); trap 'rm -rf "$$schema" "$$types"' EXIT; \
	$(OPENAPI_EXPORT) > "$$schema" && \
	$(FRONTEND) exec openapi-typescript "$$schema" -o "$$types/schema.d.ts" --silent && \
	diff -u frontend/$(API_TYPES) "$$types/schema.d.ts" || \
	{ echo "frontend/$(API_TYPES) is behind the backend's API: run make api-types and commit it." >&2; exit 1; }
