#!/bin/bash
set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

check() {
    local name="$1" cmd="$2" fix="$3"
    if command -v $cmd >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name: $($cmd --version 2>/dev/null | head -n1 || echo 'found')"
    else
        echo -e "${RED}✗${NC} $name: not found"
        [[ -n "$fix" ]] && echo -e "${BLUE}  →${NC} Install: $fix"
    fi
}

echo -e "${BLUE}SummaryLLM Doctor${NC}"
echo "------------------"

# Python >=3.11
FOUND_PY=""
for p in python3.12 python3.11 python3; do
    if command -v $p >/dev/null 2>&1; then
        v=$($p --version | awk '{print $2}')
        major=${v%%.*}; minor=${v#*.}; minor=${minor%%.*}
        if [[ $major -gt 3 || ($major -eq 3 && $minor -ge 11) ]]; then
            echo -e "${GREEN}✓${NC} Python: $v ($p)"
            FOUND_PY="$p"
            break
        fi
    fi
done
if [[ -z "$FOUND_PY" ]]; then
    echo -e "${RED}✗${NC} Python 3.11+: not found"
    if command -v brew >/dev/null 2>&1; then
        echo -e "${BLUE}  →${NC} Install: brew install python@3.11"
        echo -e "${BLUE}  →${NC} PATH: export PATH=\"\$(brew --prefix)/opt/python@3.11/bin:\$PATH\""
    elif command -v apt-get >/dev/null 2>&1; then
        echo -e "${BLUE}  →${NC} Install: sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv python3.11-dev"
    fi
fi

check "uv" "uv" "brew install uv | curl -LsSf https://astral.sh/uv/install.sh | sh"
check "docker" "docker" "brew install --cask docker | sudo apt-get install -y docker.io docker-compose"
check "curl" "curl" "brew install curl | sudo apt-get install -y curl"
check "openssl" "openssl" "brew install openssl | sudo apt-get install -y openssl"
check "git" "git" "brew install git | sudo apt-get install -y git"

echo
echo -e "${BLUE}Package managers:${NC}"
if command -v brew >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Homebrew: $(brew --version | head -n1)"
else
    echo -e "${YELLOW}⚠${NC} Homebrew: not found (recommended for macOS)"
fi

if command -v apt-get >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} apt: available"
else
    echo -e "${YELLOW}⚠${NC} apt: not found"
fi

echo
echo -e "${BLUE}Quick fix (macOS):${NC}"
echo "brew update"
echo "brew install python@3.11 uv docker openssl curl git"
echo "export PATH=\"\$(brew --prefix)/opt/python@3.11/bin:\$PATH\""
echo
echo -e "${BLUE}Quick fix (Ubuntu/Debian):${NC}"
echo "sudo apt-get update"
echo "sudo apt-get install -y python3.11 python3.11-venv python3.11-dev docker.io docker-compose curl openssl git"
