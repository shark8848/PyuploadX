.PHONY: install dev test lint build diagrams diagrams-force docs-check portal-build compose-up compose-down

install:
	python -m pip install -e ".[dev,docs]"

dev:
	uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000

test:
	python -m pytest tests -q

lint:
	ruff check app sdk upload_service tests scripts

build:
	python -m compileall -q app sdk upload_service

diagrams:
	python scripts/render_diagrams.py

diagrams-force:
	python scripts/render_diagrams.py --force

docs-check:
	python scripts/render_diagrams.py --check

portal-build:
	cd portal && npm install && npm run build

compose-up:
	docker compose -f docker-compose.yml up -d --build

compose-down:
	docker compose -f docker-compose.yml down
