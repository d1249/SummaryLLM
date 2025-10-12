#!/bin/bash
# Запуск Python с автоматическим определением окружения
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$PROJECT_DIR/.venv"

# Если venv существует, использовать его
if [[ -f "$VENV_PATH/bin/python" ]]; then
    PYTHON_BIN="$VENV_PATH/bin/python"
    echo "Используется venv: $VENV_PATH" >&2
elif command -v uv >/dev/null 2>&1; then
    # Fallback на uv run
    exec uv run python "$@"
else
    # Fallback на системный Python
    PYTHON_BIN="python3"
    echo "Используется системный Python (venv не найден)" >&2
fi

# Установить PYTHONPATH
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"

# Запустить Python
exec "$PYTHON_BIN" "$@"

