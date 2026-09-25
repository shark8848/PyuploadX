#!/usr/bin/env bash
# build-images.sh — One-shot build of every PyUploadX image.
#
# Builds (uses local base images; app layers may fetch pip/npm deps on first
# build, later builds hit the Docker cache):
#   pyuploadx-upload-api:latest  /  pyuploadx-migrate:latest  (Dockerfile target api)
#   pyuploadx-worker:latest                                    (Dockerfile target worker)
#   pyuploadx-portal:latest                                    (portal/Dockerfile)
#   pyuploadx-gateway:latest                                   (deploy/nginx/Dockerfile, OpenResty gateway)
#   pyuploadx/minio-haproxy:latest                             (deploy/minio/Dockerfile, hardened MinIO)
#
# 镜像名前缀可用 IMAGE_PREFIX 覆盖（缺省 pyuploadx-，保持原样）。ikc-demo 全栈要 ikc-* 口径时：
#   IMAGE_PREFIX=ikc-pyuploadx- bash scripts/build-images.sh --export
#     → 镜像 ikc-pyuploadx-{upload-api,migrate,worker,portal,gateway}:latest
#     → 包   docker/images/ikc-pyuploadx-*_latest.tar
# 注意：加固 MinIO（pyuploadx/minio-haproxy）不带前缀——它是本项目自带的基础件，
#       ikc 栈另用上游 minio/minio（ikc-minio / ikc-minio-mc）。
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
MINIO_HAPROXY_IMAGE="pyuploadx/minio-haproxy:latest"

EXPORT=false
if [ "${1:-}" = "--export" ]; then
    EXPORT=true
fi

echo ">>> Building app images (api / worker)... [前缀 ${IMAGE_PREFIX}]"
docker build --target api -t "$API_IMAGE" .
docker tag "$API_IMAGE" "$MIGRATE_IMAGE"
docker build --target worker -t "$WORKER_IMAGE" .

echo ">>> Building portal image..."
docker build -t "$PORTAL_IMAGE" portal/

echo ">>> Building OpenResty gateway image..."
docker build -t "$GATEWAY_IMAGE" deploy/nginx/

echo ">>> Building hardened MinIO image..."
bash deploy/minio/build.sh

if [ "$EXPORT" = true ]; then
    echo ">>> Exporting images to docker/images/ ..."
    mkdir -p docker/images
    for img in "$API_IMAGE" "$MIGRATE_IMAGE" "$WORKER_IMAGE" "$PORTAL_IMAGE" "$GATEWAY_IMAGE"; do
        out="docker/images/$(printf '%s' "$img" | tr ':/' '__').tar"
        echo "    $img → $out"
        docker save -o "$out" "$img"
    done
    docker save -o docker/images/pyuploadx__minio-haproxy_latest.tar "$MINIO_HAPROXY_IMAGE"
fi

echo ">>> Done. Project images:"
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' \
    | grep -E "^(${IMAGE_PREFIX}|pyuploadx/)" | sort
