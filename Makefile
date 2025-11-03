.PHONY: qa
qa:
	TRUNK_ALLOW_MISSING=0 TRUNK_FMT_MODE=check scripts/testing/trunk_check.sh
	uv run pytest -m "smoke"
	uv run coverage html
	@echo "Smoke QA complete. For full suite run: make qa-full"

.PHONY: qa-full
qa-full:
	TRUNK_ALLOW_MISSING=0 TRUNK_FMT_MODE=check scripts/testing/trunk_check.sh
	TRUNK_ALLOW_MISSING=0 TRUNK_SKIP_TRUNK=1 scripts/testing/full.sh

.PHONY: qa-trunk
qa-trunk:
	TRUNK_ALLOW_MISSING=0 TRUNK_FMT_MODE=check scripts/testing/trunk_check.sh

EXTRAS ?= dev orchestration
MARQUEZ_API_PORT ?= 5000
MARQUEZ_UI_PORT ?= 3000

.PHONY: sync
sync:
        @echo "Synchronising extras: $(EXTRAS)"
        @HOTPASS_UV_EXTRAS="$(EXTRAS)" bash ops/uv_sync_extras.sh

.PHONY: docs
docs:
	uv run sphinx-build -n -b html docs docs/_build/html
	@if [ "$(LINKCHECK)" = "1" ]; then \
		uv run sphinx-build -b linkcheck docs docs/_build/linkcheck; \
	else \
		echo "Skipping linkcheck (set LINKCHECK=1 to enable)"; \
	fi

.PHONY: semgrep-auto
semgrep-auto:
        @HOTPASS_CA_BUNDLE_B64="$(HOTPASS_CA_BUNDLE_B64)" bash ops/security/semgrep_auto.sh

.PHONY: marquez-up
marquez-up:
	@command -v docker >/dev/null 2>&1 || (echo "Docker CLI is required to start Marquez" >&2 && exit 1)
	@docker info >/dev/null 2>&1 || (echo "Docker daemon must be running to start Marquez" >&2 && exit 1)
	@if lsof -i tcp:$(MARQUEZ_API_PORT) >/dev/null 2>&1; then \
		echo "Port $(MARQUEZ_API_PORT) is already in use; set MARQUEZ_API_PORT to an open port" >&2; \
		exit 1; \
	fi
	@if lsof -i tcp:$(MARQUEZ_UI_PORT) >/dev/null 2>&1; then \
		echo "Port $(MARQUEZ_UI_PORT) is already in use; set MARQUEZ_UI_PORT to an open port" >&2; \
		exit 1; \
	fi
	@MARQUEZ_API_PORT=$(MARQUEZ_API_PORT) MARQUEZ_UI_PORT=$(MARQUEZ_UI_PORT) docker compose -f infra/marquez/docker-compose.yaml up -d

.PHONY: marquez-down
marquez-down:
	@command -v docker >/dev/null 2>&1 || (echo "Docker CLI is required to stop Marquez" >&2 && exit 1)
	@docker info >/dev/null 2>&1 || (echo "Docker daemon must be running to stop Marquez" >&2 && exit 1)
	@MARQUEZ_API_PORT=$(MARQUEZ_API_PORT) MARQUEZ_UI_PORT=$(MARQUEZ_UI_PORT) docker compose -f infra/marquez/docker-compose.yaml down

.PHONY: web-ui-install
web-ui-install:
	@cd apps/web-ui && npm install

.PHONY: web-ui-dev
web-ui-dev:
	@cd apps/web-ui && npm run dev

.PHONY: web-ui-build
web-ui-build:
	@cd apps/web-ui && npm run build

.PHONY: web-ui-storybook
web-ui-storybook:
	@cd apps/web-ui && npm run storybook

.PHONY: web-ui-lint
web-ui-lint:
	@cd apps/web-ui && npm run lint

# Docker Compose commands for full Hotpass stack
.PHONY: docker-up
docker-up:
	@echo "Starting Hotpass ecosystem in Docker..."
	@docker compose -f deploy/docker/docker-compose.yml up --build

.PHONY: docker-up-detached
docker-up-detached:
	@echo "Starting Hotpass ecosystem in Docker (detached)..."
	@docker compose -f deploy/docker/docker-compose.yml up --build -d

.PHONY: docker-down
docker-down:
	@echo "Stopping Hotpass ecosystem..."
	@docker compose -f deploy/docker/docker-compose.yml down

.PHONY: docker-logs
docker-logs:
	@docker compose -f deploy/docker/docker-compose.yml logs -f

.PHONY: docker-clean
docker-clean:
	@echo "Cleaning up Docker containers and volumes..."
	@docker compose -f deploy/docker/docker-compose.yml down -v
