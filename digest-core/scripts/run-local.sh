#!/bin/bash
# Local run script with convenient paths
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default paths
OUT_DIR="${OUT_DIR:-/tmp/digest-out}"
STATE_DIR="${STATE_DIR:-/tmp/digest-state}"

# Create directories if they don't exist
mkdir -p "$OUT_DIR" "$STATE_DIR"

echo "Running digest-core locally..."
echo "Output directory: $OUT_DIR"
echo "State directory: $STATE_DIR"

cd "$PROJECT_ROOT"

# Run the digest
python3 -m digest_core.cli run \
    --out "$OUT_DIR" \
    --state "$STATE_DIR" \
    --window calendar_day \
    --model gpt-4o-mini

echo "Local run completed!"
echo "Check output files in: $OUT_DIR"
