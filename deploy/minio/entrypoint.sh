#!/bin/sh
# Start MinIO on the loopback interface and expose it through HAProxy only.
set -eu

MINIO_ADDRESS="${MINIO_ADDRESS:-127.0.0.1:19000}"
MINIO_CONSOLE_ADDRESS="${MINIO_CONSOLE_ADDRESS:-127.0.0.1:19001}"

/usr/bin/minio server "$@" --address "$MINIO_ADDRESS" --console-address "$MINIO_CONSOLE_ADDRESS" &
MINIO_PID=$!

# Wait until the S3 API answers before starting HAProxy.
for _ in $(seq 1 60); do
    if wget -q -O /dev/null "http://${MINIO_ADDRESS}/minio/health/live"; then
        break
    fi
    sleep 1
done

/usr/local/sbin/haproxy -f /usr/local/etc/haproxy/haproxy.cfg &
HAPROXY_PID=$!

cleanup() {
    kill "$HAPROXY_PID" "$MINIO_PID" 2>/dev/null || true
    wait "$HAPROXY_PID" 2>/dev/null || true
    wait "$MINIO_PID" 2>/dev/null || true
}
trap cleanup TERM INT

while kill -0 "$HAPROXY_PID" 2>/dev/null && kill -0 "$MINIO_PID" 2>/dev/null; do
    sleep 1
done

cleanup
exit 1
