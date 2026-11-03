# Atajos que replican el CI (.github/workflows/ci.yml). `make check` = lo que corre en cada PR.
.PHONY: install lint typecheck test frontend-install frontend-lint frontend-test frontend-build check

install:
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check .

typecheck:
	mypy

test:
	pytest

frontend-install:
	cd frontend && npm ci

frontend-lint:
	cd frontend && npm run lint

frontend-test:
	cd frontend && npm test

frontend-build:
	cd frontend && npm run build

check: lint typecheck test frontend-lint frontend-test frontend-build
