#!/usr/bin/env bash
# build-images.sh — One-shot build of every PyUploadX image.
#
# Builds (uses local base images; app layers may fetch pip/npm deps on first
# build, later builds hit the Docker cache):
#   pyuploadx-upload-api:latest  /  pyuploadx-migrate:latest  (Dockerfile target api)
#   pyuploadx-worker:latest                                    (Dockerfile target worker)
#   pyuploadx-portal:latest                                    (portal/Dockerfile)
#   pyuploadx/minio-haproxy:latest                             (deploy/minio/Dockerfile, hardened MinIO)
#
# Usage:
#   bash scripts/build-images.sh           # build all project images
#   bash scripts/build-images.sh --export  # build, then docker save all to docker/images/
set -euo pipefail
cd "$(dirname "$0")/.."

EXPORT=false
if [ "${1:-}" = "--export" ]; then
    EXPORT=true
fi

echo ">>> Building app images (api / worker)..."
docker build --target api -t pyuploadx-upload-api:latest .
docker tag pyuploadx-upload-api:latest pyuploadx-migrate:latest
docker build --target worker -t pyuploadx-worker:latest .

echo ">>> Building portal image..."
docker build -t pyuploadx-portal:latest portal/

echo ">>> Building hardened MinIO image..."
bash deploy/minio/build.sh

if [ "$EXPORT" = true ]; then
    echo ">>> Exporting images to docker/images/ ..."
    mkdir -p docker/images
    docker save -o docker/images/pyuploadx-upload-api_latest.tar pyuploadx-upload-api:latest
    docker save -o docker/images/pyuploadx-worker_latest.tar pyuploadx-worker:latest
    docker save -o docker/images/pyuploadx-portal_latest.tar pyuploadx-portal:latest
    docker save -o docker/images/pyuploadx-migrate_latest.tar pyuploadx-migrate:latest
    docker save -o docker/images/pyuploadx__minio-haproxy_latest.tar pyuploadx/minio-haproxy:latest
fi

echo ">>> Done. Project images:"
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' \
    | grep -E '^(pyuploadx|pyuploadx/)' | sort
