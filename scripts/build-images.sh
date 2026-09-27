#!/usr/bin/env bash
# build-images.sh — One-shot build of every PyUploadX image.
#
# Builds (uses local base images; app layers may fetch pip/npm deps on first
# build, later builds hit the Docker cache):
#   pyuploadx-upload-api:latest  /  pyuploadx-migrate:latest  (Dockerfile target api)
#   pyuploadx-worker:latest                                    (Dockerfile target worker)
#   pyuploadx-portal:latest                                    (portal/Dockerfile)
#   pyuploadx-gateway:latest                                   (deploy/nginx/Dockerfile, OpenResty gateway)
#   pyuploadx-minio-haproxy:latest                             (deploy/minio/Dockerfile, hardened MinIO)
#
# 镜像名前缀可用 IMAGE_PREFIX 覆盖（缺省 pyuploadx-，保持原样）。ikc-demo 全栈要 ikc-* 口径时：
#   IMAGE_PREFIX=ikc-pyuploadx- bash scripts/build-images.sh --export
#     → 镜像 ikc-pyuploadx-{upload-api,migrate,worker,portal,gateway,minio-haproxy}:latest
#     → 包   docker/images/ikc-pyuploadx-*_latest.tar
# 六个镜像一律走同一前缀规则，加固 MinIO 也不例外（缺省 → pyuploadx-minio-haproxy:latest）；
# 需要保留历史名（pyuploadx/minio-haproxy:latest）时显式覆盖：
#   MINIO_HAPROXY_IMAGE=pyuploadx/minio-haproxy:latest bash scripts/build-images.sh
#
# Usage:
#   bash scripts/build-images.sh           # build all project images
#   bash scripts/build-images.sh --export  # build, then docker save all to docker/images/
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE_PREFIX="${IMAGE_PREFIX:-pyuploadx-}"
API_IMAGE="${IMAGE_PREFIX}upload-api:latest"
MIGRATE_IMAGE="${IMAGE_PREFIX}migrate:latest"
WORKER_IMAGE="${IMAGE_PREFIX}worker:latest"
PORTAL_IMAGE="${IMAGE_PREFIX}portal:latest"
GATEWAY_IMAGE="${IMAGE_PREFIX}gateway:latest"
MINIO_HAPROXY_IMAGE="${MINIO_HAPROXY_IMAGE:-${IMAGE_PREFIX}minio-haproxy:latest}"

EXPORT=false
if [ "${1:-}" = "--export" ]; then
    EXPORT=true
fi

# ---------------------------------------------------------------------------
# 固定版本依赖 wheel 预置（ikc-sdk-lib：Redis 单机 / 副本 / 哨兵工厂）
#   版本唯一来源 = pyproject.toml 的 == pin（不在此写死版本，避免与 pyproject 漂移）；
#   wheel 从 $IKC_SDK_LIB_DIST 复制到 docker/wheels/（Dockerfile 先装它，离线/内网构建不请求索引）。
# ---------------------------------------------------------------------------
IKC_SDK_LIB_DIST="${IKC_SDK_LIB_DIST:-/home/sharkyai/ikc-sdk-lib/dist}"

prepare_wheels() {
  local pin wheel
  pin="$(sed -n 's/^[[:space:]]*"ikc-sdk-lib==\([0-9][0-9.]*\)".*/\1/p' pyproject.toml | head -1)"
  if [[ -z "$pin" ]]; then
    echo "[err] pyproject.toml 未钉 ikc-sdk-lib==<version>" >&2
    exit 1
  fi
  wheel="${IKC_SDK_LIB_DIST}/ikc_sdk_lib-${pin}-py3-none-any.whl"
  if [[ ! -f "$wheel" ]]; then
    echo "[err] 缺少 $wheel" >&2
    echo "      先在 ikc-sdk-lib 跑 bash scripts/publish-noupload.sh 生成该版本 wheel，" >&2
    echo "      或用 IKC_SDK_LIB_DIST=<其它 dist 目录> 指向已有产物。" >&2
    exit 1
  fi
  mkdir -p docker/wheels
  rm -f docker/wheels/*.whl
  cp "$wheel" docker/wheels/
  echo "[wheel] ikc-sdk-lib ${pin} → docker/wheels/$(basename "$wheel")"
}
prepare_wheels

echo ">>> Building app images (api / worker)... [前缀 ${IMAGE_PREFIX}]"
docker build --target api -t "$API_IMAGE" .
docker tag "$API_IMAGE" "$MIGRATE_IMAGE"
docker build --target worker -t "$WORKER_IMAGE" .

echo ">>> Building portal image..."
docker build -t "$PORTAL_IMAGE" portal/

echo ">>> Building OpenResty gateway image..."
docker build -t "$GATEWAY_IMAGE" deploy/nginx/

echo ">>> Building hardened MinIO image..."
MINIO_IMAGE_TAG="$MINIO_HAPROXY_IMAGE" bash deploy/minio/build.sh

if [ "$EXPORT" = true ]; then
    echo ">>> Exporting images to docker/images/ ..."
    mkdir -p docker/images
    for img in "$API_IMAGE" "$MIGRATE_IMAGE" "$WORKER_IMAGE" "$PORTAL_IMAGE" "$GATEWAY_IMAGE" "$MINIO_HAPROXY_IMAGE"; do
        out="docker/images/$(printf '%s' "$img" | tr ':/' '__').tar"
        echo "    $img → $out"
        docker save -o "$out" "$img"
    done
fi

echo ">>> Done. Project images:"
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' \
    | grep -E "^(${IMAGE_PREFIX})" | sort
