.DEFAULT_GOAL := help

VENV := backend/.venv
PY   := $(VENV)/bin/python

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

$(VENV):
	cd backend && uv venv .venv && uv pip install -p .venv -e ".[dev]"

install: $(VENV) ## Install backend venv and frontend node_modules
	cd frontend && npm install

dev: $(VENV) ## Run API with auto-reload (frontend: `cd frontend && npm run dev`)
	cd backend && .venv/bin/uvicorn codeguide.main:app --reload

runners: ## Build the sandbox runner images
	docker build -t coding-learning-ai-guide-runner-python:latest -f runners/python/Dockerfile runners
	docker build -t coding-learning-ai-guide-runner-node:latest -f runners/node/Dockerfile runners

DOCKER_GID := $(shell stat -c '%g' /var/run/docker.sock 2>/dev/null || echo 999)

demo: runners ## One-command demo: build, start the stack, seed sample data
	DOCKER_GID=$(DOCKER_GID) docker compose up -d --build --wait
	docker compose exec -T api python -m codeguide.cli seed
	@echo ""
	@echo "  Web UI:  http://localhost:8080"
	@echo "  API:     http://localhost:8000/api/docs"
	@echo ""
	@echo "  Join a course with one of the codes printed above."

seed: ## (Re-)seed demo data into the running stack
	docker compose exec -T api python -m codeguide.cli seed

test: $(VENV) ## Backend unit tests
	cd backend && .venv/bin/pytest

test-integration: $(VENV) runners ## Backend integration tests (needs Docker)
	cd backend && .venv/bin/pytest -m integration

lint: $(VENV) ## Lint backend and frontend
	cd backend && .venv/bin/ruff check src tests
	cd frontend && npm run lint

typecheck: $(VENV) ## mypy (backend) and tsc (frontend)
	cd backend && .venv/bin/mypy
	cd frontend && npx tsc -b

screenshots: ## Capture dashboard screenshots from the running demo stack
	cd frontend && npx playwright test e2e/screenshots.spec.ts

diagrams: ## Export README/docs Mermaid diagrams to docs/images
	bash scripts/export-diagrams.sh

kind-demo: ## Stand up the full stack on a local kind cluster
	bash deploy/kind/demo.sh

clean: ## Stop the stack and remove local state
	docker compose down -v --remove-orphans
	rm -rf backend/data

.PHONY: help install dev runners demo seed test test-integration lint typecheck screenshots diagrams kind-demo clean
