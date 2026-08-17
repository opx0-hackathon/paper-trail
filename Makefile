.DEFAULT_GOAL := help
.PHONY: help install fmt lint typecheck test live serve shots all

help: ## list targets
	@grep -hE '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | sed -e 's/:.*##/\t/' | expand -t 12

install: ## create the environment from uv.lock
	uv sync

fmt: ## format the tree
	uv run ruff format .

lint: ## check formatting and lint rules
	uv run ruff format --check .
	uv run ruff check .

typecheck: ## mypy strict over the package
	uv run mypy src

test: ## the fast suite, no network
	uv run pytest

live: ## the one test that really calls the model
	LIVE=1 uv run pytest -m live

serve: ## serve the app on http://127.0.0.1:8790
	uv run papertrail-serve

web: ## build the interface
	cd web && npm ci && npm run typecheck && npm run test && npm run build

all: lint typecheck test ## everything CI runs for the api, in CI order
