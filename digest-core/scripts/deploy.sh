#!/bin/bash
# Deploy script for Docker container
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Deploying digest-core..."

cd "$PROJECT_ROOT"

# Build Docker image
echo "Building Docker image..."
docker build -t digest-core:latest -f docker/Dockerfile .

# Check if Docker image was built successfully
if [ $? -ne 0 ]; then
    echo "Error: Docker build failed"
    exit 1
fi

# Example deployment command
echo "Docker image built successfully!"
echo ""
echo "To run the container:"
echo "docker run -d \\"
echo "  --name digest-core \\"
echo "  -e EWS_PASSWORD='your_password' \\"
echo "  -e LLM_TOKEN='your_token' \\"
echo "  -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro \\"
echo "  -v /opt/digest/out:/data/out \\"
echo "  -v /opt/digest/.state:/data/.state \\"
echo "  -p 9108:9108 \\"
echo "  -p 9109:9109 \\"
echo "  digest-core:latest"
echo ""
echo "To run manually:"
echo "docker run -it \\"
echo "  -e EWS_PASSWORD='your_password' \\"
echo "  -e LLM_TOKEN='your_token' \\"
echo "  -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro \\"
echo "  -v /opt/digest/out:/data/out \\"
echo "  -v /opt/digest/.state:/data/.state \\"
echo "  -p 9108:9108 \\"
echo "  -p 9109:9109 \\"
echo "  digest-core:latest python -m digest_core.cli run"
