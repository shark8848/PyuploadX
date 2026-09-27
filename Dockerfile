FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/upload-service

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY upload_service ./upload_service
COPY sdk ./sdk

# 固定版本依赖的预置 wheel（ikc_sdk_lib：Redis 单机/副本/哨兵工厂）。有则先装，让下面的
# -e ".[log-center]" 不必请求索引；没有则回落索引（PyPI 已发布该版本），保持 docker build 可用。
# wheel 由 scripts/build-images.sh 按 pyproject.toml 的 == pin 派生后放进 docker/wheels/。
COPY docker/wheels/ /tmp/wheels/
RUN if ls /tmp/wheels/*.whl >/dev/null 2>&1; then pip install --no-cache-dir /tmp/wheels/*.whl; fi

RUN pip install --no-cache-dir -e ".[log-center]"

FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

FROM base AS worker
CMD ["python", "-m", "app.worker.main"]
