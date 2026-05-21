#!/usr/bin/env bash
#
# End-to-end smoke test: spin up the image, wait for readiness, run a few
# /analyze checks, tear it down. Exits non-zero on any failure.
#
# Usage: ./scripts/e2e.sh <image-tag> [host-port]
#        ./scripts/e2e.sh hoophq/presidio-analyzer:dev 3000

set -euo pipefail

IMAGE="${1:-hoophq/presidio-analyzer:latest}"
PORT="${2:-${PORT:-3000}}"
CONTAINER="presidio-analyzer-e2e-$$"

cleanup() {
    docker stop "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo ">>> starting $IMAGE on :$PORT"
docker run -d --rm --name "$CONTAINER" -p "$PORT:3000" "$IMAGE" >/dev/null

echo ">>> waiting for /supportedentities ..."
ready=false
for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "http://localhost:$PORT/supportedentities" 2>/dev/null; then
        ready=true
        break
    fi
    sleep 1
done

if [ "$ready" != "true" ]; then
    echo "!!! analyzer did not become ready within 60s" >&2
    docker logs "$CONTAINER" 2>&1 | tail -40 >&2
    exit 1
fi

echo ">>> /supportedentities includes BR_CPF?"
if curl -fsS "http://localhost:$PORT/supportedentities" | tr ',' '\n' | grep -q BR_CPF; then
    echo "    yes"
else
    echo "!!! BR_CPF missing from /supportedentities" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANALYZER="$SCRIPT_DIR/analyzer-test.sh"

# Valid CPF must be detected.
echo
echo ">>> valid CPF should be detected"
ANALYZER_URL="http://localhost:$PORT" "$ANALYZER" "CPF: 111.444.777-35" | tee /tmp/e2e-valid.out
grep -q "BR_CPF" /tmp/e2e-valid.out || { echo "!!! BR_CPF not detected"; exit 3; }

# Off-by-one checksum must NOT be detected.
echo
echo ">>> invalid checksum should NOT be detected"
ANALYZER_URL="http://localhost:$PORT" "$ANALYZER" "CPF: 111.444.777-36" | tee /tmp/e2e-invalid.out
grep -q "BR_CPF" /tmp/e2e-invalid.out && { echo "!!! BR_CPF falsely detected on bad checksum"; exit 4; }

# All-same-digit must NOT be detected.
echo
echo ">>> all-same-digit should NOT be detected"
ANALYZER_URL="http://localhost:$PORT" "$ANALYZER" "11111111111" | tee /tmp/e2e-same.out
grep -q "BR_CPF" /tmp/e2e-same.out && { echo "!!! BR_CPF falsely detected on repeated digits"; exit 5; }

echo
echo ">>> e2e ok"
