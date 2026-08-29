.PHONY: install dev test lint build migrate diagrams diagrams-force docs-check portal-build compose-up compose-down benchmark test-minio

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

migrate:
	alembic upgrade head

diagrams:
	python scripts/render_diagrams.py

diagrams-force:
	python scripts/render_diagrams.py --force

docs-check:
	python scripts/render_diagrams.py --check
	python scripts/check_docs.py

portal-build:
	cd portal && npm install && npm run build

compose-up:
	bash scripts/start-stack.sh

compose-down:
	docker compose -f docker-compose.yml down

benchmark:
	python scripts/benchmark_upload.py

test-minio:
	UPLOAD_MINIO_TEST=1 python -m pytest tests/integration/test_s3_storage.py -q
