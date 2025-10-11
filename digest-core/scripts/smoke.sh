#!/bin/bash
# Smoke test script with dry-run and basic EWS check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Running smoke tests..."

cd "$PROJECT_ROOT"

# Check if the CLI is available
if ! python3 -m digest_core.cli --help &> /dev/null; then
    echo "Error: digest_core CLI not available. Run 'uv sync' first."
    exit 1
fi

# Run dry-run test
echo "Running dry-run test..."
python3 -m digest_core.cli run --dry-run --window calendar_day

if [ $? -eq 2 ]; then
    echo "Dry-run test passed (exit code 2 as expected)"
else
    echo "Dry-run test failed"
    exit 1
fi

# Basic EWS connectivity check (if credentials are available)
if [ -n "${EWS_PASSWORD:-}" ] && [ -n "${EWS_USER_UPN:-}" ]; then
    echo "Testing EWS connectivity..."
    python3 -c "
from digest_core.ingest.ews import EWSIngester
from digest_core.config import Config
try:
    config = Config()
    ingester = EWSIngester(config)
    print('EWS configuration loaded successfully')
except Exception as e:
    print(f'EWS configuration error: {e}')
    exit(1)
"
else
    echo "EWS credentials not available, skipping connectivity test"
fi

echo "Smoke tests completed successfully!"
