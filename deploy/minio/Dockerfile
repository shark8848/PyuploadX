# syntax=docker/dockerfile:1
# Hardened MinIO image: MinIO binds to the loopback interface only and is
# exposed exclusively through HAProxy, so MinIO's HTTP endpoints are never
# reachable directly. Builds from locally cached base images (no registry
# access required): minio/minio provides the static minio binary and
# haproxy:3.0-alpine provides HAProxy plus the runtime.
#
# Build:  bash deploy/minio/build.sh
# Run:    docker run -d --name pyuploadx-minio --restart unless-stopped \
#           -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
#           -v /data/minio:/data -p 9000:9000 -p 9001:9001 \
#           pyuploadx/minio-haproxy:latest /data

ARG MINIO_BASE_IMAGE=minio/minio:latest
FROM ${MINIO_BASE_IMAGE} AS minio

FROM haproxy:3.0-alpine AS runtime

COPY --from=minio /usr/bin/minio /usr/bin/minio
COPY haproxy.cfg /usr/local/etc/haproxy/haproxy.cfg
COPY entrypoint.sh /entrypoint.sh

ENV MINIO_ADDRESS=127.0.0.1:19000 \
    MINIO_CONSOLE_ADDRESS=127.0.0.1:19001

# The haproxy base image defaults to the unprivileged `haproxy` user; MinIO
# needs write access to the root-owned /data volume, so run as root (same as
# the official minio/minio image).
USER root

EXPOSE 9000 9001
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1:9000/minio/health/live || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/data"]
