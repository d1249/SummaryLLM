#!/bin/bash
# Helper Python launcher for digest-core
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Prefer local venv if exists
if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PY="$PROJECT_ROOT/.venv/bin/python"
else
  # Fallback to system python3
  if command -v python3 >/dev/null 2>&1; then
    PY="python3"
  else
    PY="python"
  fi
fi

export PYTHONPATH="$PROJECT_ROOT/src:${PYTHONPATH:-}"
exec "$PY" "$@"

