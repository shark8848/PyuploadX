#!/usr/bin/env bash
# Build the hardened MinIO image (MinIO + HAProxy front) from local base
# images, so no registry access is required. Override the target tag or the
# MinIO base image via MINIO_IMAGE_TAG / MINIO_BASE_IMAGE.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE_TAG="${MINIO_IMAGE_TAG:-pyuploadx/minio-haproxy:latest}"
MINIO_BASE_IMAGE="${MINIO_BASE_IMAGE:-minio/minio:latest}"

docker build \
    --build-arg MINIO_BASE_IMAGE="$MINIO_BASE_IMAGE" \
    -t "$IMAGE_TAG" \
    .

echo "built ${IMAGE_TAG} (base: ${MINIO_BASE_IMAGE})" >&2
