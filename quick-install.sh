#!/bin/bash
set -euo pipefail

# SummaryLLM Quick Installer (Non-Interactive)
# Usage: curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/quick-install.sh | bash

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_header() { echo -e "${PURPLE}$1${NC}"; }
print_step() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# Configuration
REPO_URL="https://github.com/your-org/SummaryLLM.git"
INSTALL_DIR="$HOME/SummaryLLM"

print_header "🚀 SummaryLLM Quick Installer"
echo "=================================="

# Clone repository
print_step "Cloning Repository"
if [[ -d "$INSTALL_DIR" ]]; then
    print_info "Directory exists, updating..."
    cd "$INSTALL_DIR" && git pull
else
    print_info "Cloning to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install dependencies
print_step "Installing Dependencies"
cd digest-core

if command -v uv >/dev/null 2>&1; then
    print_info "Installing with uv..."
    uv sync
elif command -v pip >/dev/null 2>&1; then
    print_info "Installing with pip..."
    pip install -e .
else
    print_info "No package manager found, skipping Python deps"
fi

cd ..

# Create minimal .env template
print_step "Creating Configuration Template"
cat > .env.template << 'EOF'
# SummaryLLM Environment Variables
# Copy this file to .env and fill in your values

# EWS Configuration
EWS_PASSWORD="your_ews_password"
EWS_USER_UPN="user@corp.com"
EWS_ENDPOINT="https://ews.corp.com/EWS/Exchange.asmx"

# LLM Configuration
LLM_TOKEN="your_llm_token"
LLM_ENDPOINT="https://llm-gw.corp.com/api/v1/chat"
EOF

# Create minimal config template
mkdir -p digest-core/configs
cat > digest-core/configs/config.template.yaml << 'EOF'
# SummaryLLM Configuration Template
# Copy this file to config.yaml and customize

time:
  user_timezone: "Europe/Moscow"
  window: "calendar_day"

ews:
  endpoint: "${EWS_ENDPOINT}"
  user_upn: "${EWS_USER_UPN}"
  password_env: "EWS_PASSWORD"
  verify_ca: ""
  autodiscover: false
  folders: ["Inbox"]
  lookback_hours: 24
  page_size: 100
  sync_state_path: ".state/ews.syncstate"

llm:
  endpoint: "${LLM_ENDPOINT}"
  model: "corp/gpt-4o-mini"
  timeout_s: 45
  headers:
    Authorization: "Bearer ${LLM_TOKEN}"
  max_tokens_per_run: 30000
  cost_limit_per_run: 5.0

observability:
  prometheus_port: 9108
  log_level: "INFO"
EOF

print_success "Quick installation complete!"

echo
print_header "Next Steps:"
echo "1. cd $INSTALL_DIR"
echo "2. cp .env.template .env"
echo "3. cp digest-core/configs/config.template.yaml digest-core/configs/config.yaml"
echo "4. Edit .env and config.yaml with your settings"
echo "5. cd digest-core && python -m digest_core.cli run --dry-run"
echo
print_info "For interactive setup, run: ./setup.sh"
print_info "For full documentation, see: README.md"
