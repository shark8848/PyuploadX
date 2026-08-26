#!/bin/sh
# 初始化 MinIO buckets（docs 25）：首次部署或重建后执行。
set -eu
MC="${MC:-mc}"
ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
ACCESS_KEY="${MINIO_ROOT_USER:-minioadmin}"
SECRET_KEY="${MINIO_ROOT_PASSWORD:-minioadmin}"

"$MC" alias set local "$ENDPOINT" "$ACCESS_KEY" "$SECRET_KEY"
for bucket in app-default public-assets; do
  "$MC" mb --ignore-existing "local/$bucket"
done
"$MC" anonymous set download local/public-assets
echo "minio bootstrap complete"
