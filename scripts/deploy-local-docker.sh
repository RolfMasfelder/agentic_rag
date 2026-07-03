#!/usr/bin/env bash
set -euo pipefail

# Build and start the local agentic_rag stack (db, redis, web, worker).
# Builds images with a versioned tag, optionally pushes to the local registry.
#
# Usage:
#   ./scripts/deploy-local-docker.sh            # build + start
#   ./scripts/deploy-local-docker.sh --no-cache # force full rebuild
#   ./scripts/deploy-local-docker.sh --push     # also push to local registry

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"

# Read deploy target from .env (required for --push)
REGISTRY=$(grep -E '^DEPLOY_REGISTRY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)

COMPOSE="docker compose -f docker/docker-compose.yml --env-file .env"
EXTRA_ARGS=()
PUSH=false

for arg in "$@"; do
  case "$arg" in
    --push)     PUSH=true ;;
    --no-cache) EXTRA_ARGS+=("--no-cache") ;;
    *)          EXTRA_ARGS+=("$arg") ;;
  esac
done

# Build versioned tag: v<version>-<git-sha>
VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
GIT_SHA=$(git rev-parse --short HEAD)
TAG="v${VERSION}-${GIT_SHA}"

echo "=== agentic_rag – Local Deploy (tag: ${TAG}) ==="
echo "    Registry: ${REGISTRY} (push: ${PUSH})"
echo ""

# Step 1: Build images with versioned tag
echo "[1/3] Building images (tag: ${TAG})..."
IMAGE_TAG=${TAG} ${COMPOSE} build "${EXTRA_ARGS[@]}" web worker
echo "  ✓ Images built"

# Step 2: Optionally push to local registry for versioning/rollback
if [[ "${PUSH}" == "true" ]]; then
  if [[ -z "${REGISTRY}" ]]; then
    echo "  ✗ DEPLOY_REGISTRY is not set in .env, cannot --push." >&2
    exit 1
  fi
  echo "[2/3] Pushing images to registry ${REGISTRY}..."
  docker push "${REGISTRY}/agentic_rag-web:${TAG}"
  docker push "${REGISTRY}/agentic_rag-worker:${TAG}"
  echo "  ✓ Images pushed"
else
  echo "[2/3] Skipping registry push (pass --push to enable)"
fi

# Step 3: Start / restart local stack
echo "[3/3] Starting local stack..."
IMAGE_TAG=${TAG} ${COMPOSE} up -d --no-build
echo "  ✓ Stack started"

echo ""
echo "=== Local deploy complete (tag: ${TAG}) ==="
echo "Verify with: docker compose -f docker/docker-compose.yml ps"
