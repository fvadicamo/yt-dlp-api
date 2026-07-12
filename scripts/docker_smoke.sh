#!/usr/bin/env bash
# Container smoke test: boots the image in test mode and exercises the
# HTTP surface from outside the container (liveness, docs, auth
# rejection, mocked video info, metrics).
#
# Usage: docker_smoke.sh <image> [docker-cli-args...]
#   SMOKE_PORT      host port to bind (default 18000)
#   DOCKER          docker command (default "docker"), e.g. "docker --context rootless"

set -euo pipefail

IMAGE="${1:?usage: docker_smoke.sh <image>}"
DOCKER="${DOCKER:-docker}"
PORT="${SMOKE_PORT:-18000}"
NAME="ytdlp-smoke-$$"
API_KEY="ci-smoke-key"
DEMO_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"

COOKIE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/smoke-cookies.XXXXXX")

cleanup() {
    $DOCKER rm -f "$NAME" >/dev/null 2>&1 || true
    if [ -n "${COOKIE_DIR:-}" ]; then
        rm -rf "$COOKIE_DIR"
    fi
}
trap cleanup EXIT

# Dummy Netscape cookie file, same pattern as tests/e2e/conftest.py:
# test mode mocks yt-dlp but the provider still requires a configured
# cookie file to load.
printf '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1999999999\tCONSENT\tYES+\n' \
    > "${COOKIE_DIR}/youtube.txt"
# World-readable: the container user (uid 1000) differs from the host
# user creating the fixture (runner uid, or a rootless-mapped uid).
chmod 755 "$COOKIE_DIR"
chmod 644 "${COOKIE_DIR}/youtube.txt"

echo "Starting container from ${IMAGE}..."
$DOCKER run -d --name "$NAME" -p "${PORT}:8000" \
    -v "${COOKIE_DIR}:/app/cookies:ro" \
    -e APP_TESTING_TEST_MODE=true \
    -e APP_SECURITY_ALLOW_DEGRADED_START=true \
    -e APP_YOUTUBE_COOKIE_PATH=/app/cookies/youtube.txt \
    -e "APP_SECURITY_API_KEYS=[\"${API_KEY}\"]" \
    "$IMAGE" >/dev/null

echo "Waiting for liveness..."
for i in {1..30}; do
    if curl -fsS "http://127.0.0.1:${PORT}/liveness" >/dev/null 2>&1; then
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "FAIL: liveness timeout after 60s"
        $DOCKER logs "$NAME" 2>&1 | tail -50
        exit 1
    fi
    sleep 2
done

check() {
    local name="$1" expected="$2"
    shift 2
    local status
    # `|| true`: under set -e a connection failure inside the command
    # substitution would kill the script before the diagnostics below.
    status=$(curl -s -o /dev/null -w "%{http_code}" "$@" || true)
    if [ "$status" != "$expected" ]; then
        echo "FAIL: ${name} expected HTTP ${expected}, got ${status}"
        $DOCKER logs "$NAME" 2>&1 | tail -50
        exit 1
    fi
    echo "OK: ${name} (${status})"
}

check "liveness" 200 "http://127.0.0.1:${PORT}/liveness"
check "openapi docs" 200 "http://127.0.0.1:${PORT}/docs"
check "metrics" 200 "http://127.0.0.1:${PORT}/metrics"
check "auth rejected without key" 401 \
    "http://127.0.0.1:${PORT}/api/v1/info?url=${DEMO_URL}"
check "video info (mocked)" 200 \
    -H "X-API-Key: ${API_KEY}" \
    "http://127.0.0.1:${PORT}/api/v1/info?url=${DEMO_URL}"
check "transcript (mocked)" 200 \
    -H "X-API-Key: ${API_KEY}" \
    "http://127.0.0.1:${PORT}/api/v1/transcript?url=${DEMO_URL}&fmt=text"

echo "Container smoke test passed."
