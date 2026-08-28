#!/usr/bin/env bash
# publish-pypi-server.sh — Build and upload the pyuploadx-server backend to PyPI.
#
# The server distribution builds from the repo root (packages app/ + upload_service/).
# The SDK distribution is published separately by publish-pypi.sh.
#
# Usage:
#   ./scripts/publish-pypi-server.sh                        # Full build + upload
#   PYUPX_SERVER_VERSION=0.2.0 ./scripts/publish-pypi-server.sh   # Specify version
#   ./scripts/publish-pypi-server.sh --test                 # Upload to TestPyPI
#   ./scripts/publish-pypi-server.sh --skip-build           # Reuse existing dist/
#   ./scripts/publish-pypi-server.sh --no-skip-existing     # Fail if version exists
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config/pypi.env"

SKIP_BUILD=false
SKIP_EXISTING=true
REPOSITORY_URL=""

for arg in "$@"; do
    case "$arg" in
        --skip-build)      SKIP_BUILD=true ;;
        --no-skip-existing) SKIP_EXISTING=false ;;
        --test)            REPOSITORY_URL="https://test.pypi.org/legacy/" ;;
        -h|--help)
            echo "Usage: $0 [--skip-build] [--no-skip-existing] [--test]"
            echo ""
            echo "  --skip-build        Reuse existing dist/ artifacts"
            echo "  --no-skip-existing  Fail if version already exists on PyPI"
            echo "  --test              Upload to TestPyPI instead of PyPI"
            echo ""
            echo "Environment variables:"
            echo "  PYUPX_SERVER_VERSION  Override server version (default: pyproject.toml)"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: $CONFIG_FILE not found."
    echo "Copy the template and fill in your PyPI token:"
    echo "  cp config/pypi.env.example config/pypi.env"
    exit 1
fi

# shellcheck source=/dev/null
source "$CONFIG_FILE"

PYPI_USERNAME="${PYUPX_PYPI_USERNAME:-__token__}"
PYPI_TOKEN="${PYUPX_PYPI_TOKEN:-}"
if [ -z "$PYPI_TOKEN" ] || [ "$PYPI_TOKEN" = "replace_with_your_pypi_api_token" ]; then
    echo "ERROR: PYUPX_PYPI_TOKEN not set in $CONFIG_FILE"
    exit 1
fi

if [ -n "$REPOSITORY_URL" ]; then
    :
elif [ -n "${PYUPX_PYPI_REPOSITORY_URL:-}" ]; then
    REPOSITORY_URL="$PYUPX_PYPI_REPOSITORY_URL"
else
    REPOSITORY_URL="https://upload.pypi.org/legacy/"
fi

CURRENT_VERSION=$(grep -m1 '^version' "$ROOT_DIR/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')
PACKAGE_VERSION="${PYUPX_SERVER_VERSION:-$CURRENT_VERSION}"

echo "========================================"
echo " pyuploadx-server publish"
echo " Version:    $PACKAGE_VERSION"
echo " Repository: $REPOSITORY_URL"
echo "========================================"

cd "$ROOT_DIR"

if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo ">>> Cleaning build dirs and current-version artifacts only..."
    rm -rf build/ *.egg-info
    rm -f "dist/pyuploadx_server-${PACKAGE_VERSION}-"*.whl "dist/pyuploadx_server-${PACKAGE_VERSION}.tar.gz"

    RESTORE_VERSION=false
    if [ -n "${PYUPX_SERVER_VERSION:-}" ] && [ "$PYUPX_SERVER_VERSION" != "$CURRENT_VERSION" ]; then
        echo ">>> Overriding version: $CURRENT_VERSION → $PYUPX_SERVER_VERSION"
        sed -i "s/^version = \".*\"/version = \"$PYUPX_SERVER_VERSION\"/" pyproject.toml
        RESTORE_VERSION=true
    fi

    echo ">>> Installing build tools..."
    python -m pip install --upgrade build twine --quiet

    echo ">>> Building wheel + sdist..."
    python -m build

    if [ "$RESTORE_VERSION" = true ]; then
        sed -i "s/^version = \".*\"/version = \"$CURRENT_VERSION\"/" pyproject.toml
    fi
else
    echo ""
    echo ">>> Skipping build (--skip-build), using existing dist/"
    if [ ! -d dist ] || [ -z "$(ls -A dist/pyuploadx_server-*.whl 2>/dev/null)" ]; then
        echo "ERROR: No pyuploadx-server wheel found in dist/. Run without --skip-build first."
        exit 1
    fi
fi

echo ""
echo ">>> Artifacts:"
ls -lh dist/pyuploadx_server-*

echo ""
echo ">>> Uploading to $REPOSITORY_URL ..."

TWINE_ARGS=(
    upload
    --username "$PYPI_USERNAME"
    --password "$PYPI_TOKEN"
    --repository-url "$REPOSITORY_URL"
)

if [ "$SKIP_EXISTING" = true ]; then
    TWINE_ARGS+=(--skip-existing)
fi

TWINE_ARGS+=(dist/pyuploadx_server-*.whl dist/pyuploadx_server-*.tar.gz)

python -m twine "${TWINE_ARGS[@]}"

echo ""
echo "✅ Published pyuploadx-server $PACKAGE_VERSION to $REPOSITORY_URL"
echo "   NOTE: dist/ artifacts are committed to the repo (all historical versions retained)."
