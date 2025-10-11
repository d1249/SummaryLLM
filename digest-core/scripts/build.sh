#!/bin/bash
# Build script for digest-core package and Docker image
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building digest-core package..."

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "Error: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install dependencies
cd "$PROJECT_ROOT"
echo "Installing dependencies with uv..."
uv sync

# Build package (if needed)
echo "Building package..."
uv build

# Build Docker image
echo "Building Docker image..."
docker build -t digest-core:latest -f docker/Dockerfile .

echo "Build completed successfully!"
echo "Docker image: digest-core:latest"
