#!/usr/bin/env bash
# publish-pypi.sh — Build and upload pyuploadx (Python SDK + service) to PyPI.
#
# Usage:
#   ./scripts/publish-pypi.sh                          # Full build + upload
#   PYUPX_VERSION=0.2.0 ./scripts/publish-pypi.sh      # Specify version
#   ./scripts/publish-pypi.sh --test                   # Upload to TestPyPI
#   ./scripts/publish-pypi.sh --skip-build             # Reuse existing dist/
#   ./scripts/publish-pypi.sh --no-skip-existing       # Fail if version exists
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config/pypi.env"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
SKIP_BUILD=false
SKIP_EXISTING=true
REPOSITORY_URL=""

# ---------------------------------------------------------------------------
# Parse CLI flags
# ---------------------------------------------------------------------------
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
            echo "  PYUPX_VERSION  Override package version (default: pyproject.toml)"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Load credentials
# ---------------------------------------------------------------------------
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
    # --test flag overrides
    :
elif [ -n "${PYUPX_PYPI_REPOSITORY_URL:-}" ]; then
    REPOSITORY_URL="$PYUPX_PYPI_REPOSITORY_URL"
else
    REPOSITORY_URL="https://upload.pypi.org/legacy/"
fi

# ---------------------------------------------------------------------------
# Version override
# ---------------------------------------------------------------------------
CURRENT_VERSION=$(grep -m1 '^version' "$ROOT_DIR/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')
PACKAGE_VERSION="${PYUPX_VERSION:-$CURRENT_VERSION}"

echo "========================================"
echo " pyuploadx publish"
echo " Version:    $PACKAGE_VERSION"
echo " Repository: $REPOSITORY_URL"
echo "========================================"

cd "$ROOT_DIR"

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo ">>> Cleaning build dirs and current-version artifacts only..."
    echo "    (dist/ keeps historical version artifacts; never wipe them)"
    rm -rf build/ *.egg-info src/*.egg-info sdk/*.egg-info
    rm -f "dist/pyuploadx-${PACKAGE_VERSION}-"*.whl "dist/pyuploadx-${PACKAGE_VERSION}.tar.gz"

    # Temporarily override version if PYUPX_VERSION is set
    RESTORE_VERSION=false
    if [ -n "${PYUPX_VERSION:-}" ] && [ "$PYUPX_VERSION" != "$CURRENT_VERSION" ]; then
        echo ">>> Overriding version: $CURRENT_VERSION → $PYUPX_VERSION"
        sed -i "s/^version = \".*\"/version = \"$PYUPX_VERSION\"/" pyproject.toml
        sed -i "s/^__version__ = \".*\"/__version__ = \"$PYUPX_VERSION\"/" sdk/pyuploadx/__init__.py
        RESTORE_VERSION=true
    fi

    echo ">>> Installing build tools..."
    python -m pip install --upgrade build twine --quiet

    echo ">>> Building wheel + sdist..."
    python -m build

    # Restore original version if we changed it
    if [ "$RESTORE_VERSION" = true ]; then
        sed -i "s/^version = \".*\"/version = \"$CURRENT_VERSION\"/" pyproject.toml
        sed -i "s/^__version__ = \".*\"/__version__ = \"$CURRENT_VERSION\"/" sdk/pyuploadx/__init__.py
    fi
else
    echo ""
    echo ">>> Skipping build (--skip-build), using existing dist/"
    if [ ! -d dist ] || [ -z "$(ls -A dist/*.whl 2>/dev/null)" ]; then
        echo "ERROR: No .whl found in dist/. Run without --skip-build first."
        exit 1
    fi
fi

echo ""
echo ">>> Artifacts:"
ls -lh dist/

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
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

TWINE_ARGS+=(dist/*.whl dist/*.tar.gz)

python -m twine "${TWINE_ARGS[@]}"

echo ""
echo "✅ Published pyuploadx $PACKAGE_VERSION to $REPOSITORY_URL"
echo "   NOTE: dist/ artifacts are committed to the repo (all historical versions retained)."
