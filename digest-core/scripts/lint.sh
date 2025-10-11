#!/bin/bash
# Lint script with ruff, black, and mypy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Running linting checks..."

cd "$PROJECT_ROOT"

# Check if linting tools are available
if ! command -v ruff &> /dev/null; then
    echo "Error: ruff not found. Install with: uv add ruff"
    exit 1
fi

if ! command -v black &> /dev/null; then
    echo "Error: black not found. Install with: uv add black"
    exit 1
fi

# Run ruff for linting
echo "Running ruff linting..."
ruff check src/ tests/

# Run black for formatting check
echo "Running black formatting check..."
black --check src/ tests/

# Run mypy for type checking (if available)
if command -v mypy &> /dev/null; then
    echo "Running mypy type checking..."
    mypy src/digest_core/
else
    echo "mypy not available, skipping type checking"
fi

echo "Linting completed successfully!"
