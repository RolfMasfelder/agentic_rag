#!/usr/bin/env bash
set -euo pipefail

# Ensures required Ollama models are available on the remote host.
# The agentic_rag project re-uses the stt-ollama container that is already
# running there — no second Ollama container is created.
#
# Usage: ./scripts/deploy-remote-docker.sh

REGISTRY="192.168.178.80:5000"
REMOTE_HOST="192.168.178.80"
REMOTE_USER="rolf"

# ── Pfade ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"

# Build versioned tag for logging: v<version>-<git-sha>
VERSION=$(python -c "import tomllib; print(tomllib.load(open('$REPO_ROOT/pyproject.toml','rb'))['project']['version'])")
GIT_SHA=$(git -C "$REPO_ROOT" rev-parse --short HEAD)
TAG="v${VERSION}-${GIT_SHA}"

# Read Ollama model names from .env (fall back to defaults)
EMBED_MODEL=$(grep -E '^OLLAMA_EMBED_MODEL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
EMBED_MODEL="${EMBED_MODEL:-nomic-embed-text:latest}"

CHAT_MODEL=$(grep -E '^OLLAMA_CHAT_MODEL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
CHAT_MODEL="${CHAT_MODEL:-qwen3.5:9b}"

echo "=== agentic_rag – Remote Ollama Setup (tag: ${TAG}) ==="
echo "    Registry:    ${REGISTRY}"
echo "    Remote host: ${REMOTE_USER}@${REMOTE_HOST}"
echo "    Embed model: ${EMBED_MODEL}"
echo "    Chat model:  ${CHAT_MODEL}"
echo ""

# Step 1: Verify stt-ollama container is running on remote
echo "[1/2] Checking stt-ollama container on ${REMOTE_HOST}..."
OLLAMA_RUNNING=$(ssh "${REMOTE_USER}@${REMOTE_HOST}" \
  "docker ps -q --filter name=stt-ollama 2>/dev/null | head -1 || true")

if [[ -z "${OLLAMA_RUNNING}" ]]; then
  echo "  ✗ stt-ollama container is not running on ${REMOTE_HOST}." >&2
  echo "    Start the STT stack first, then re-run this script." >&2
  exit 1
fi
echo "  ✓ stt-ollama is running (container id: ${OLLAMA_RUNNING})"

# Step 2: Pull required models (idempotent — no-op if already present)
echo "[2/2] Ensuring models are pulled in stt-ollama..."
ssh "${REMOTE_USER}@${REMOTE_HOST}" "
  echo '  Pulling embed model: ${EMBED_MODEL}...'
  docker exec stt-ollama ollama pull ${EMBED_MODEL}
  echo '  ✓ ${EMBED_MODEL} ready'

  echo '  Pulling chat model: ${CHAT_MODEL}...'
  docker exec stt-ollama ollama pull ${CHAT_MODEL}
  echo '  ✓ ${CHAT_MODEL} ready'
"

echo ""
echo "=== Remote Ollama setup complete ==="
echo "OLLAMA_BASE_URL=http://${REMOTE_HOST}:11434  (set in .env)"
