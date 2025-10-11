#!/bin/bash
# Environment diagnostics script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Digest-core environment diagnostics..."
echo "======================================"

# Check Python version
echo "Python version:"
python3 --version

# Check required tools
echo ""
echo "Required tools:"
for tool in uv docker pytest ruff black; do
    if command -v "$tool" &> /dev/null; then
        echo "✓ $tool: $(which $tool)"
    else
        echo "✗ $tool: not found"
    fi
done

# Check environment variables (without showing values)
echo ""
echo "Environment variables:"
for var in EWS_USER_UPN EWS_PASSWORD LLM_TOKEN EWS_ENDPOINT LLM_ENDPOINT; do
    if [ -n "${!var:-}" ]; then
        echo "✓ $var: set (${#!var} characters)"
    else
        echo "✗ $var: not set"
    fi
done

# Check CA certificate
echo ""
echo "CA certificate:"
if [ -f "/etc/ssl/corp-ca.pem" ]; then
    echo "✓ Corporate CA found: /etc/ssl/corp-ca.pem"
    echo "  Certificate info:"
    openssl x509 -in /etc/ssl/corp-ca.pem -text -noout | grep -E "(Subject:|Not Before|Not After)" || true
else
    echo "✗ Corporate CA not found: /etc/ssl/corp-ca.pem"
fi

# Check directories
echo ""
echo "Directory permissions:"
for dir in /opt/digest/out /opt/digest/.state; do
    if [ -d "$dir" ]; then
        echo "✓ $dir: exists (permissions: $(stat -c %a "$dir"))"
    else
        echo "✗ $dir: does not exist"
    fi
done

# Check network connectivity
echo ""
echo "Network connectivity:"
if ping -c 1 8.8.8.8 &> /dev/null; then
    echo "✓ Internet connectivity: OK"
else
    echo "✗ Internet connectivity: failed"
fi

# Check if we can resolve EWS endpoint (if set)
if [ -n "${EWS_ENDPOINT:-}" ]; then
    echo "EWS endpoint: $EWS_ENDPOINT"
    if curl -s --connect-timeout 5 "$EWS_ENDPOINT" &> /dev/null; then
        echo "✓ EWS endpoint reachable"
    else
        echo "✗ EWS endpoint not reachable"
    fi
fi

echo ""
echo "Diagnostics completed!"
