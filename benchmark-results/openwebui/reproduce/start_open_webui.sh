#!/bin/bash
# Open WebUI launcher — clean restart with correct plural env vars.
#
# Required env vars (caller must export before invoking):
#   OPENROUTER_API_KEY    your OpenRouter key, used as the upstream provider
#   IFIXAI_REPO_ROOT      absolute path to the iFixAi checkout that hosts the
#                         .venv-openwebui virtual environment

: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY must be exported}"
: "${IFIXAI_REPO_ROOT:?IFIXAI_REPO_ROOT must be exported (path to the iFixAi repo)}"

export WEBUI_AUTH=True
export ENABLE_SIGNUP=True
export ENABLE_OPENAI_API=True
export ENABLE_OLLAMA_API=False

# CORRECT plural env vars (semicolon-separated lists)
export OPENAI_API_BASE_URLS="https://openrouter.ai/api/v1"
export OPENAI_API_KEYS="$OPENROUTER_API_KEY"

export DEFAULT_MODELS="anthropic/claude-sonnet-4.6"
export WEBUI_SECRET_KEY="${WEBUI_SECRET_KEY:-change-me-in-real-deployments}"
export PORT="${PORT:-8080}"
export WEBUI_NAME="OpenWebUI-Bench"
export DATA_DIR="${DATA_DIR:-/tmp/owui-data}"
export ENABLE_API_KEY=True

mkdir -p "$DATA_DIR"
cd "$IFIXAI_REPO_ROOT"
exec .venv-openwebui/bin/open-webui serve --port "$PORT" --host 127.0.0.1
