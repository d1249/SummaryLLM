#!/bin/bash
set -eo pipefail

# SummaryLLM One-Command Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/install.sh | bash
# Or: curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/install.sh | bash -s -- --help

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/d1249/SummaryLLM.git"
DEFAULT_INSTALL_DIR="$HOME/SummaryLLM"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Options
INSTALL_DIR=""
SKIP_DEPS="false"
SKIP_SETUP="false"
VERBOSE="false"
HELP="false"

# New options
AUTO_BREW="false"
AUTO_APT="false"
PYTHON_REQUESTED=""
NON_INTERACTIVE="false"
ADD_PATH="false"

# Resolved python executable (>=3.11)
PYTHON_BIN=""

# Helper functions
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_header() {
    echo -e "${PURPLE}$1${NC}"
}

print_step() {
    echo -e "\n${CYAN}=== $1 ===${NC}"
}

# Check if running from existing repository
is_existing_repo() {
    [[ -f "$SCRIPT_DIR/setup.sh" ]] && [[ -d "$SCRIPT_DIR/digest-core" ]]
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --skip-deps)
                SKIP_DEPS="true"
                shift
                ;;
            --skip-setup)
                SKIP_SETUP="true"
                shift
                ;;
            --verbose|-v)
                VERBOSE="true"
                shift
                ;;
            --auto-brew|-y)
                AUTO_BREW="true"
                shift
                ;;
            --auto-apt)
                AUTO_APT="true"
                shift
                ;;
            --python)
                PYTHON_REQUESTED="$2"
                shift 2
                ;;
            --non-interactive)
                NON_INTERACTIVE="true"
                shift
                ;;
            --add-path)
                ADD_PATH="true"
                shift
                ;;
            --help|-h)
                HELP="true"
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
SummaryLLM One-Command Installer

USAGE:
    curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/install.sh | bash
    curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/install.sh | bash -s -- [OPTIONS]

OPTIONS:
    --install-dir DIR     Installation directory (default: \$HOME/SummaryLLM)
    --skip-deps          Skip dependency installation
    --skip-setup         Skip interactive setup wizard
    --verbose, -v        Verbose output
    --auto-brew, -y      Auto-install missing deps via Homebrew (no prompts)
    --auto-apt           Auto-install missing deps via apt (no prompts)
    --python VER         Prefer Python version (e.g. 3.11 or 3.12)
    --non-interactive    Disable prompts; use auto flags or fail with instructions
    --add-path           Append Homebrew Python bin dir to ~/.zshrc
    --help, -h           Show this help

EXAMPLES:
    # Basic installation
    curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/install.sh | bash
    
    # Install to custom directory
    curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/install.sh | bash -s -- --install-dir /opt/summaryllm
    
    # Auto-install missing deps via Homebrew and add PATH for python@3.11
    PATH="\$(brew --prefix)/opt/python@3.11/bin:\$PATH" scripts/install.sh --auto-brew --add-path

WHAT THIS SCRIPT DOES:
    1. Clones SummaryLLM repository
    2. Checks and installs dependencies (Python 3.11+, uv, docker, etc.)
    3. Runs interactive setup wizard
    4. Installs Python dependencies
    5. Provides next steps

REQUIREMENTS:
    - Git
    - Internet connection
    - sudo access (for dependency installation)

EOF
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Find Python 3.11+ executable
find_python() {
    local requested="$1"
    local candidates=()

    # Respect explicit request first
    if [[ -n "$requested" ]]; then
        candidates+=("python${requested}" "python${requested%.*}")
    fi

    # Common binaries
    candidates+=("python3.12" "python3.11" "python3")

    # Homebrew direct paths (even if not in PATH)
    if command -v brew >/dev/null 2>&1; then
        local bp
        bp="$(brew --prefix 2>/dev/null || true)"
        if [[ -n "$bp" ]]; then
            candidates+=("$bp/opt/python@3.12/bin/python3.12")
            candidates+=("$bp/opt/python@3.11/bin/python3.11")
        fi
    fi

    for bin in "${candidates[@]}"; do
        if command -v "$bin" >/dev/null 2>&1; then
            local resolved
            resolved="$(command -v "$bin")"
            local v="$("$resolved" --version | awk '{print $2}')"
            local major="${v%%.*}"
            local minor="${v#*.}"; minor="${minor%%.*}"
            if [[ "$major" -gt 3 || ("$major" -eq 3 && "$minor" -ge 11) ]]; then
                echo "$resolved"
                return 0
            fi
        elif [[ -x "$bin" ]]; then
            local v="$("$bin" --version | awk '{print $2}')"
            local major="${v%%.*}"
            local minor="${v#*.}"; minor="${minor%%.*}"
            if [[ "$major" -gt 3 || ("$major" -eq 3 && "$minor" -ge 11) ]]; then
                echo "$bin"
                return 0
            fi
        fi
    done

    return 1
}

# Add Homebrew python@3.11 bin to PATH in ~/.zshrc
add_brew_python_path() {
    # Adds Homebrew python@3.11 bin to PATH in ~/.zshrc
    if ! command -v brew >/dev/null 2>&1; then
        return 0
    fi
    local bp
    bp="$(brew --prefix 2>/dev/null || true)"
    if [[ -z "$bp" ]]; then
        return 0
    fi
    local line='export PATH="'"$bp"'/opt/python@3.11/bin:$PATH"'
    if [[ "$ADD_PATH" == "true" ]]; then
        if ! grep -qs 'opt/python@3.11/bin' "$HOME/.zshrc"; then
            echo "$line" >> "$HOME/.zshrc"
            print_success "Added python@3.11 to PATH in ~/.zshrc"
            print_info "Reload shell: exec zsh -l"
        fi
    else
        print_info "To use python@3.11, consider adding:"
        echo "  $line"
        echo "  exec zsh -l"
    fi
}

# Check dependencies
check_dependencies() {
    print_step "Checking Dependencies"

    local missing_tools=()

    # Check Git
    if command_exists "git"; then
        print_success "Git found"
    else
        print_error "Git not found"
        missing_tools+=("git")
    fi

    # Python >=3.11 via find_python
    PYTHON_BIN="$(find_python "$PYTHON_REQUESTED" || true)"
    if [[ -n "$PYTHON_BIN" ]]; then
        local python_version="$("$PYTHON_BIN" --version | cut -d' ' -f2)"
        print_success "Python $python_version found at $PYTHON_BIN"
    else
        print_error "Python 3.11+ not found"
        missing_tools+=("python3")
    fi

    # Check other tools
    for tool in uv docker curl openssl; do
        if command_exists "$tool"; then
            print_success "$tool found"
        else
            print_error "$tool not found"
            missing_tools+=("$tool")
        fi
    done

    # Nothing missing
    if [[ ${#missing_tools[@]} -eq 0 ]]; then
        return
    fi

    if [[ "$SKIP_DEPS" == "true" ]]; then
        print_warning "Missing tools detected but --skip-deps specified: ${missing_tools[*]}"
        print_info "You may need to install these manually before running SummaryLLM"
        return
    fi

    # Auto / interactive install
    if command_exists "brew"; then
        if [[ "$AUTO_BREW" == "true" || "$NON_INTERACTIVE" == "true" ]]; then
            print_info "Installing missing tools via Homebrew (non-interactive)..."
            install_dependencies "${missing_tools[@]}"
        else
            read -p "Install missing tools via Homebrew? [y/N]: " install_choice
            if [[ "$install_choice" =~ ^[Yy]$ ]]; then
                install_dependencies "${missing_tools[@]}"
            else
                print_error "Cannot proceed without required tools"
                print_info "Manual install example (macOS):"
                echo "  brew install python@3.11 uv docker openssl curl git"
                exit 1
            fi
        fi
    elif command_exists "apt-get"; then
        if [[ "$AUTO_APT" == "true" || "$NON_INTERACTIVE" == "true" ]]; then
            print_info "Installing missing tools via apt (non-interactive)..."
            install_dependencies_apt "${missing_tools[@]}"
        else
            read -p "Install missing tools via apt? [y/N]: " install_choice
            if [[ "$install_choice" =~ ^[Yy]$ ]]; then
                install_dependencies_apt "${missing_tools[@]}"
            else
                print_error "Cannot proceed without required tools"
                print_info "Manual install example (Ubuntu/Debian):"
                echo "  sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv python3.11-dev docker.io docker-compose curl openssl git"
                exit 1
            fi
        fi
    else
        print_error "No supported package manager found. Please install manually: ${missing_tools[*]}"
        exit 1
    fi

    # Re-check Python after installation
    if [[ -z "$PYTHON_BIN" ]]; then
        PYTHON_BIN="$(find_python "$PYTHON_REQUESTED" || true)"
        if [[ -z "$PYTHON_BIN" ]]; then
            # On macOS, suggest PATH for Homebrew python
            if command_exists brew; then
                add_brew_python_path
                # Try again after advising PATH (user may re-run)
            fi
            print_error "Python 3.11+ still not available in PATH"
            echo "Try:"
            echo "  brew install python@3.11"
            echo "  export PATH=\"\$(brew --prefix)/opt/python@3.11/bin:\$PATH\""
            exit 1
        else
            local python_version="$("$PYTHON_BIN" --version | cut -d' ' -f2)"
            print_success "Python $python_version found at $PYTHON_BIN"
        fi
    fi
}

# Install dependencies via Homebrew (macOS)
install_dependencies() {
    local tools=("$@")
    
    print_info "Installing dependencies via Homebrew..."
    
    for tool in "${tools[@]}"; do
        case "$tool" in
            "python3")
                print_info "Installing Python 3.11+ via Homebrew..."
                brew install python@3.11
                ;;
            "uv")
                print_info "Installing uv via Homebrew..."
                brew install uv
                ;;
            "docker")
                print_info "Installing Docker Desktop via Homebrew..."
                brew install --cask docker
                ;;
            "curl"|"openssl")
                print_info "Installing $tool via Homebrew..."
                brew install "$tool"
                ;;
            "git")
                print_info "Installing Git via Homebrew..."
                brew install git
                ;;
        esac
    done
}

# Install dependencies via apt (Ubuntu/Debian)
install_dependencies_apt() {
    local tools=("$@")
    
    print_info "Installing dependencies via apt..."
    
    # Update package list
    sudo apt-get update
    
    for tool in "${tools[@]}"; do
        case "$tool" in
            "python3")
                print_info "Installing Python 3.11+ via apt..."
                sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
                ;;
            "uv")
                print_info "Installing uv via apt..."
                curl -LsSf https://astral.sh/uv/install.sh | sh
                ;;
            "docker")
                print_info "Installing Docker via apt..."
                sudo apt-get install -y docker.io docker-compose
                sudo usermod -aG docker $USER
                ;;
            "curl"|"openssl")
                print_info "Installing $tool via apt..."
                sudo apt-get install -y "$tool"
                ;;
            "git")
                print_info "Installing Git via apt..."
                sudo apt-get install -y git
                ;;
        esac
    done
}

# Clone repository
clone_repository() {
    print_step "Cloning Repository"
    
    if [[ -z "$INSTALL_DIR" ]]; then
        INSTALL_DIR="$DEFAULT_INSTALL_DIR"
    fi
    
    # Check if directory already exists
    if [[ -d "$INSTALL_DIR" ]]; then
        print_warning "Directory $INSTALL_DIR already exists"
        read -p "Do you want to remove it and reinstall? [y/N]: " remove_choice
        if [[ "$remove_choice" =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
            print_info "Removed existing directory"
        else
            print_error "Installation cancelled"
            exit 1
        fi
    fi
    
    # Clone repository
    print_info "Cloning SummaryLLM to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    
    # Change to installation directory
    cd "$INSTALL_DIR"
    
    print_success "Repository cloned successfully"
}

# Run setup wizard
run_setup() {
    print_step "Running Setup Wizard"
    
    if [[ "$SKIP_SETUP" == "true" ]]; then
        print_info "Skipping setup wizard (--skip-setup specified)"
        return
    fi
    
    if [[ -f "./scripts/setup.sh" ]]; then
        print_info "Running interactive setup wizard..."
        chmod +x ./scripts/setup.sh
        # Change to the cloned directory before running setup
        cd "$INSTALL_DIR"
        # Pass found Python binary to setup.sh and ensure interactive mode
        if [[ -n "$PYTHON_BIN" ]]; then
            PYTHON_BIN="$PYTHON_BIN" ./scripts/setup.sh < /dev/tty
        else
            ./scripts/setup.sh < /dev/tty
        fi
    elif [[ -f "./setup.sh" ]]; then
        print_info "Running interactive setup wizard..."
        chmod +x ./setup.sh
        # Change to the cloned directory before running setup
        cd "$INSTALL_DIR"
        # Pass found Python binary to setup.sh and ensure interactive mode
        if [[ -n "$PYTHON_BIN" ]]; then
            PYTHON_BIN="$PYTHON_BIN" ./setup.sh < /dev/tty
        else
            ./setup.sh < /dev/tty
        fi
    else
        print_error "setup.sh not found in repository"
        exit 1
    fi
}

# Install Python dependencies
install_python_deps() {
    print_step "Installing Python Dependencies"

    if [[ -d "digest-core" ]]; then
        cd digest-core

        if command_exists "uv"; then
            print_info "Installing dependencies with uv..."
            # Try with native TLS first (for corporate networks)
            if uv sync --native-tls; then
                print_success "Dependencies installed with native TLS"
            else
                print_warning "Native TLS failed, trying standard sync..."
                uv sync
            fi
        elif command_exists "pip" || [[ -n "$PYTHON_BIN" ]]; then
            print_info "Installing dependencies with pip..."
            if [[ -n "$PYTHON_BIN" ]]; then
                "$PYTHON_BIN" -m pip install -e .
            else
                pip install -e .
            fi
        else
            print_warning "Neither uv nor pip found, skipping Python dependency installation"
            cd ..
            return
        fi

        cd ..
        print_success "Python dependencies installed"
    else
        print_error "digest-core directory not found"
        exit 1
    fi
}

# Show next steps
show_next_steps() {
    print_step "Installation Complete!"
    
    echo
    print_header "Next Steps:"
    echo "1. Change to installation directory:"
    echo "   cd $INSTALL_DIR"
    echo
    echo "2. Activate environment (if not done in setup):"
    echo "   source .env"
    echo
    echo "3. Run your first digest:"
    echo "   cd digest-core"
    echo "   # Test run (prefer uv, fallback to PYTHONPATH)"
    echo "   if command -v uv >/dev/null 2>&1; then"
    echo "     uv run python -m digest_core.cli run --dry-run"
    echo "   else"
    echo "     PYTHONPATH=./src ${PYTHON_BIN:-python3} -m digest_core.cli run --dry-run"
    echo "   fi"
    echo
    echo "4. For full documentation, see:"
    echo "   - README.md (quick start)"
    echo "   - digest-core/README.md (detailed docs)"
    echo "   - DEPLOYMENT.md (deployment guide)"
    echo "   - AUTOMATION.md (automation guide)"
    echo "   - MONITORING.md (monitoring guide)"
    echo
    
    print_success "SummaryLLM is ready to use! 🎉"
}

# Main function
main() {
    # Show help if requested
    if [[ "$HELP" == "true" ]]; then
        show_help
        exit 0
    fi
    
    # Welcome message
    echo
    print_header "🚀 SummaryLLM One-Command Installer"
    echo "=============================================="
    echo
    
    # Check if running from existing repository
    if is_existing_repo; then
        print_info "Running from existing SummaryLLM repository"
        INSTALL_DIR="$SCRIPT_DIR"
    else
        # Parse arguments
        parse_args "$@"
        
        # Check dependencies
        check_dependencies
        
        # After check_dependencies (may have installed python@3.11)
        if [[ -z "$PYTHON_BIN" ]]; then
            PYTHON_BIN="$(find_python "$PYTHON_REQUESTED" || true)"
        fi
        if command_exists brew; then
            add_brew_python_path
        fi
        
        # Clone repository
        clone_repository
    fi
    
    # Run setup wizard
    run_setup
    
    # Install Python dependencies
    install_python_deps
    
    # Show next steps
    show_next_steps
}

# Handle script interruption
trap 'print_error "Installation interrupted"; exit 1' INT TERM

# Run main function
main "$@"
# Updated Sun Oct 12 13:53:51 MSK 2025
