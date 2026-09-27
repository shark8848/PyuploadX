#!/usr/bin/env bash
# Build the hardened MinIO image (MinIO + HAProxy front) from local base
# images, so no registry access is required. The tag follows the same
# IMAGE_PREFIX rule as scripts/build-images.sh; override it directly with
# MINIO_IMAGE_TAG, or the MinIO base image with MINIO_BASE_IMAGE.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE_PREFIX="${IMAGE_PREFIX:-pyuploadx-}"
IMAGE_TAG="${MINIO_IMAGE_TAG:-${IMAGE_PREFIX}minio-haproxy:latest}"
MINIO_BASE_IMAGE="${MINIO_BASE_IMAGE:-minio/minio:latest}"

docker build \
    --build-arg MINIO_BASE_IMAGE="$MINIO_BASE_IMAGE" \
    -t "$IMAGE_TAG" \
    .

echo "built ${IMAGE_TAG} (base: ${MINIO_BASE_IMAGE})" >&2
