#!/bin/bash
set -eo pipefail

# SummaryLLM Interactive Setup Script
# This script guides users through configuring SummaryLLM by collecting
# all necessary parameters, validating connectivity, and generating configuration files.

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIGEST_CORE_DIR="$PROJECT_ROOT/digest-core"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
VERBOSE="${VERBOSE:-false}"

# Use Python binary passed from install.sh if available
if [[ -n "${PYTHON_BIN:-}" ]]; then
    FOUND_PYTHON="$PYTHON_BIN"
else
    FOUND_PYTHON=""
fi

# Collected configuration (using individual variables instead of associative array for compatibility)
EWS_ENDPOINT=""
EWS_USER_UPN=""
EWS_LOGIN=""
EWS_DOMAIN=""
EWS_PASSWORD=""
EWS_CA_CERT=""
EWS_FOLDERS=""
EWS_LOOKBACK_HOURS=""
LLM_ENDPOINT=""
LLM_TOKEN=""
LLM_MODEL=""
LLM_TIMEOUT=""
LLM_MAX_TOKENS=""
TIMEZONE=""
WINDOW_TYPE=""
PROMETHEUS_PORT=""
LOG_LEVEL=""
PAGE_SIZE=""
COST_LIMIT=""
SYNC_STATE_PATH=""

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

# Validation functions
validate_email() {
    local email="$1"
    if [[ $email =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        return 0
    else
        return 1
    fi
}

validate_url() {
    local url="$1"
    if [[ $url =~ ^https?:// ]]; then
        return 0
    else
        return 1
    fi
}

validate_https() {
    local url="$1"
    if [[ $url =~ ^https:// ]]; then
        return 0
    else
        return 1
    fi
}

check_tool() {
    local tool="$1"
    if command -v "$tool" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

backup_file() {
    local file_path="$1"
    if [[ -f "$file_path" ]]; then
        local backup_path="${file_path}.backup.${TIMESTAMP}"
        cp "$file_path" "$backup_path"
        print_warning "Found existing $(basename "$file_path") file"
        print_info "Creating backup: $(basename "$backup_path")"
        return 0
    fi
    return 1
}

# Backup tracking variables
ENV_BACKED_UP="false"
CONFIG_BACKED_UP="false"

check_connectivity() {
    local url="$1"
    local timeout="${2:-10}"
    
    if curl -s --connect-timeout "$timeout" --max-time "$timeout" "$url" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

validate_certificate() {
    local cert_path="$1"
    if [[ -f "$cert_path" ]]; then
        if openssl x509 -in "$cert_path" -text -noout &> /dev/null; then
            return 0
        else
            return 1
        fi
    else
        return 1
    fi
}

test_ews_ntlm_connection() {
    print_info "Тестирование NTLM-подключения к EWS..."
    
    # Create temporary file for FindItem SOAP request
    local finditem_xml=$(mktemp)
    cat > "$finditem_xml" << 'SOAP_EOF'
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
  <soap:Body>
    <FindItem Traversal="Shallow" xmlns="http://schemas.microsoft.com/exchange/services/2006/messages">
      <ItemShape>
        <t:BaseShape>IdOnly</t:BaseShape>
      </ItemShape>
      <ParentFolderIds>
        <t:DistinguishedFolderId Id="inbox"/>
      </ParentFolderIds>
    </FindItem>
  </soap:Body>
</soap:Envelope>
SOAP_EOF
    
    # Execute NTLM request
    local ntlm_user="${EWS_LOGIN}@${EWS_DOMAIN}"
    print_info "Попытка подключения с логином: $ntlm_user"
    
    local response
    response=$(curl -s --ntlm -u "$ntlm_user:$EWS_PASSWORD" \
        -H 'Content-Type: text/xml; charset=utf-8' \
        -H 'SOAPAction: http://schemas.microsoft.com/exchange/services/2006/messages/FindItem' \
        --data @"$finditem_xml" \
        --max-time 30 \
        "$EWS_ENDPOINT" 2>&1)
    
    local curl_exit_code=$?
    rm -f "$finditem_xml"
    
    # Check result
    if [[ $curl_exit_code -ne 0 ]]; then
        print_error "Ошибка выполнения curl (код: $curl_exit_code)"
        print_info "Проверьте сетевую доступность endpoint"
        return 1
    fi
    
    if echo "$response" | grep -q "ResponseCode"; then
        if echo "$response" | grep -q "NoError"; then
            print_success "NTLM-аутентификация успешна!"
            return 0
        elif echo "$response" | grep -q "ErrorAccessDenied"; then
            print_error "Ошибка доступа - проверьте логин/пароль"
            return 1
        else
            print_warning "Получен ответ от сервера, но не NoError"
            if [[ "$VERBOSE" == "true" ]]; then
                echo "$response" | head -20
            fi
            return 0
        fi
    else
        print_error "Не получен корректный SOAP-ответ от EWS"
        print_info "Проверьте endpoint и сетевую доступность"
        if [[ "$VERBOSE" == "true" ]]; then
            echo "$response" | head -20
        fi
        return 1
    fi
}

# Prompt functions
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    # Ensure we're reading from terminal
    if [[ ! -t 0 ]]; then
        echo "Error: This script requires interactive input. Please run it directly, not through pipes." >&2
        exit 1
    fi
    
    if [[ -n "$default" ]]; then
        echo -n "$prompt [$default]: "
        read input
        eval "$var_name=\"\${input:-$default}\""
    else
        echo -n "$prompt: "
        read input
        eval "$var_name=\"$input\""
    fi
}

prompt_password() {
    local prompt="$1"
    local var_name="$2"
    
    # Ensure we're reading from terminal
    if [[ ! -t 0 ]]; then
        echo "Error: This script requires interactive input. Please run it directly, not through pipes." >&2
        exit 1
    fi
    
    echo -n "$prompt: "
    read -s password
    echo
    eval "$var_name=\"$password\""
}

prompt_choice() {
    local prompt="$1"
    local options="$2"
    local default="$3"
    local var_name="$4"
    
    echo "$prompt"
    local i=1
    for option in $options; do
        if [[ "$option" == "$default" ]]; then
            echo "  $i) $option (default)"
        else
            echo "  $i) $option"
        fi
        ((i++))
    done
    
    # Ensure we're reading from terminal
    if [[ ! -t 0 ]]; then
        echo "Error: This script requires interactive input. Please run it directly, not through pipes." >&2
        exit 1
    fi
    
    echo -n "Choose option [1]: "
    read choice
    choice="${choice:-1}"
    
    local options_array=($options)
    local selected_option="${options_array[$((choice-1))]}"
    eval "$var_name=\"\${selected_option:-$default}\""
}

# Main functions
check_dependencies() {
    print_step "Checking Dependencies"
    
    local missing_tools=()
    
    # Check Python - use passed Python binary if available
    if [[ -n "$FOUND_PYTHON" ]]; then
        local python_version=$("$FOUND_PYTHON" --version | cut -d' ' -f2)
        print_success "Python $python_version found at $FOUND_PYTHON"
        
        # Check if Python version is 3.11+
        local major=$(echo "$python_version" | cut -d'.' -f1)
        local minor=$(echo "$python_version" | cut -d'.' -f2)
        if [[ $major -lt 3 ]] || [[ $major -eq 3 && $minor -lt 11 ]]; then
            print_error "Python 3.11+ required, found $python_version"
            missing_tools+=("python3")
        fi
    elif check_tool "python3"; then
        local python_version=$(python3 --version | cut -d' ' -f2)
        print_success "Python $python_version found"
        
        # Check if Python version is 3.11+
        local major=$(echo "$python_version" | cut -d'.' -f1)
        local minor=$(echo "$python_version" | cut -d'.' -f2)
        if [[ $major -lt 3 ]] || [[ $major -eq 3 && $minor -lt 11 ]]; then
            print_error "Python 3.11+ required, found $python_version"
            missing_tools+=("python3")
        fi
    else
        print_error "Python 3.11+ not found"
        missing_tools+=("python3")
    fi
    
    # Check other tools
    for tool in uv docker curl openssl; do
        if check_tool "$tool"; then
            print_success "$tool found"
        else
            print_error "$tool not found"
            missing_tools+=("$tool")
        fi
    done
    
    # Offer to install missing tools via Homebrew
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        echo
        print_warning "Missing tools: ${missing_tools[*]}"
        
        if check_tool "brew"; then
            echo -n "Would you like to install missing tools via Homebrew? [y/N]: "
            read install_choice
            if [[ "$install_choice" =~ ^[Yy]$ ]]; then
                for tool in "${missing_tools[@]}"; do
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
                    esac
                done
            else
                print_error "Cannot proceed without required tools"
                exit 1
            fi
        else
            print_error "Homebrew not found. Please install missing tools manually: ${missing_tools[*]}"
            exit 1
        fi
    fi
}

setup_venv() {
    print_step "Настройка виртуального окружения Python"
    
    local venv_path="$DIGEST_CORE_DIR/.venv"
    
    # Проверить, существует ли уже venv
    if [[ -d "$venv_path" ]]; then
        print_info "Виртуальное окружение уже существует: $venv_path"
        read -p "Пересоздать venv? [y/N]: " recreate
        if [[ "$recreate" =~ ^[Yy]$ ]]; then
            print_info "Удаление старого venv..."
            rm -rf "$venv_path"
        else
            print_success "Используем существующее виртуальное окружение"
            return 0
        fi
    fi
    
    # Создать venv
    print_info "Создание виртуального окружения в $venv_path..."
    if [[ -n "$FOUND_PYTHON" ]]; then
        "$FOUND_PYTHON" -m venv "$venv_path"
    else
        python3 -m venv "$venv_path"
    fi
    
    if [[ $? -eq 0 ]]; then
        print_success "Виртуальное окружение создано"
    else
        print_error "Не удалось создать виртуальное окружение"
        exit 1
    fi
    
    # Обновить pip в venv
    print_info "Обновление pip в виртуальном окружении..."
    "$venv_path/bin/pip" install --upgrade pip setuptools wheel > /dev/null 2>&1
    
    if [[ $? -eq 0 ]]; then
        print_success "Виртуальное окружение готово"
    else
        print_warning "Не удалось обновить pip, но venv создано"
    fi
}

backup_configs() {
    print_step "Backing Up Existing Configuration"
    
    # Backup .env file
    if backup_file "$PROJECT_ROOT/.env"; then
        ENV_BACKED_UP="true"
    fi
    
    # Backup config.yaml
    if backup_file "$DIGEST_CORE_DIR/configs/config.yaml"; then
        CONFIG_BACKED_UP="true"
    fi
    
    if [[ "$ENV_BACKED_UP" != "true" ]] && [[ "$CONFIG_BACKED_UP" != "true" ]]; then
        print_info "No existing configuration files found"
    fi
}

collect_ews_config() {
    print_step "EWS Configuration"
    
    # 1. User login for NTLM
    prompt_with_default "Введите ваш логин (например, ivanov)" "" "EWS_LOGIN"
    while [[ -z "$EWS_LOGIN" ]]; do
        print_error "Логин не может быть пустым"
        prompt_with_default "Введите ваш логин (например, ivanov)" "" "EWS_LOGIN"
    done
    print_success "Логин: $EWS_LOGIN"
    
    # 2. Corporate email (UPN)
    while true; do
        prompt_with_default "Введите корпоративную почту" "" "EWS_USER_UPN"
        if validate_email "$EWS_USER_UPN"; then
            print_success "Валидный email: $EWS_USER_UPN"
            break
        else
            print_error "Введите корректный email адрес"
        fi
    done
    
    # 3. Extract domain from email
    EWS_DOMAIN="${EWS_USER_UPN#*@}"
    print_info "Домен определён как: $EWS_DOMAIN"
    
    # 4. EWS endpoint with default based on domain
    while true; do
        prompt_with_default "Введите EWS endpoint URL" "https://owa.$EWS_DOMAIN/EWS/Exchange.asmx" "EWS_ENDPOINT"
        if validate_https "$EWS_ENDPOINT"; then
            print_success "Валидный HTTPS URL"
            break
        else
            print_error "Введите корректный HTTPS URL"
        fi
    done
    
    # 5. Password
    prompt_password "Введите пароль EWS" "EWS_PASSWORD"
    print_success "Пароль получен"
    
    # Corporate CA certificate
    prompt_with_default "Путь к корпоративному CA сертификату (оставьте пустым для пропуска)" "" "EWS_CA_CERT"
    if [[ -n "$EWS_CA_CERT" ]]; then
        if validate_certificate "$EWS_CA_CERT"; then
            print_success "Файл сертификата найден и валиден"
        else
            print_error "Неверный файл сертификата или путь"
            EWS_CA_CERT=""
        fi
    fi
    
    # Folders
    prompt_with_default "Папки для обработки (через запятую)" "Inbox" "EWS_FOLDERS"
    
    # Lookback hours
    while true; do
        prompt_with_default "Период просмотра (часы)" "24" "EWS_LOOKBACK_HOURS"
        if [[ "$EWS_LOOKBACK_HOURS" =~ ^[0-9]+$ ]] && [[ "$EWS_LOOKBACK_HOURS" -gt 0 ]]; then
            break
        else
            print_error "Введите положительное число"
        fi
    done
}

collect_llm_config() {
    print_step "LLM Configuration"
    
    # LLM endpoint
    while true; do
        prompt_with_default "Enter LLM Gateway endpoint URL" "" "LLM_ENDPOINT"
        if validate_https "$LLM_ENDPOINT"; then
            print_success "Valid HTTPS URL"
            break
        else
            print_error "Please enter a valid HTTPS URL"
        fi
    done
    
    # LLM token
    prompt_password "Enter LLM API token" "LLM_TOKEN"
    print_success "Token captured"
    
    # Model name
    prompt_with_default "Model name" "Qwen/Qwen3-30B-A3B-Instruct-2507" "LLM_MODEL"
    
    # Timeout
    while true; do
        prompt_with_default "Timeout seconds" "60" "LLM_TIMEOUT"
        if [[ "$LLM_TIMEOUT" =~ ^[0-9]+$ ]] && [[ "$LLM_TIMEOUT" -gt 0 ]]; then
            break
        else
            print_error "Please enter a positive number"
        fi
    done
    
    # Max tokens
    while true; do
        prompt_with_default "Max tokens per run" "30000" "LLM_MAX_TOKENS"
        if [[ "$LLM_MAX_TOKENS" =~ ^[0-9]+$ ]] && [[ "$LLM_MAX_TOKENS" -gt 0 ]]; then
            break
        else
            print_error "Please enter a positive number"
        fi
    done
}

collect_time_config() {
    print_step "Time Configuration"
    
    # Timezone
    prompt_with_default "Timezone" "Europe/Moscow" "TIMEZONE"
    
    # Window type
    prompt_choice "Select time window type:" "calendar_day rolling_24h" "calendar_day" "WINDOW_TYPE"
}

collect_observability_config() {
    print_step "Observability Configuration"
    
    # Prometheus port
    while true; do
        prompt_with_default "Prometheus port" "9108" "PROMETHEUS_PORT"
        if [[ "$PROMETHEUS_PORT" =~ ^[0-9]+$ ]] && [[ "$PROMETHEUS_PORT" -ge 1024 ]] && [[ "$PROMETHEUS_PORT" -le 65535 ]]; then
            break
        else
            print_error "Please enter a valid port number (1024-65535)"
        fi
    done
    
    # Log level
    prompt_choice "Select log level:" "DEBUG INFO WARNING ERROR" "INFO" "LOG_LEVEL"
}

collect_advanced_config() {
    print_step "Advanced Configuration (Optional)"
    
    echo -n "Would you like to configure advanced settings? [y/N]: "
    read advanced_choice
    if [[ "$advanced_choice" =~ ^[Yy]$ ]]; then
        # Page size
        while true; do
            prompt_with_default "Page size for pagination" "100" "PAGE_SIZE"
            if [[ "$PAGE_SIZE" =~ ^[0-9]+$ ]] && [[ "$PAGE_SIZE" -gt 0 ]]; then
                break
            else
                print_error "Please enter a positive number"
            fi
        done
        
        # Cost limit
        while true; do
            prompt_with_default "Cost limit per run (USD)" "5.0" "COST_LIMIT"
            if [[ "$COST_LIMIT" =~ ^[0-9]+\.?[0-9]*$ ]] && [[ $(echo "$COST_LIMIT > 0" | bc -l) -eq 1 ]]; then
                break
            else
                print_error "Please enter a positive number"
            fi
        done
        
        # Sync state path
        prompt_with_default "Sync state path" ".state/ews.syncstate" "SYNC_STATE_PATH"
    else
        # Set defaults
        PAGE_SIZE="100"
        COST_LIMIT="5.0"
        SYNC_STATE_PATH=".state/ews.syncstate"
    fi
}

validate_connectivity() {
    print_step "Validating Configuration"
    
    # Test EWS connectivity
    print_info "Testing EWS connectivity..."
    if check_connectivity "$EWS_ENDPOINT" 10; then
        print_success "EWS endpoint reachable"
    else
        print_error "EWS endpoint not reachable"
        print_warning "This might be normal if the endpoint requires authentication"
    fi
    
    # Test EWS NTLM authentication
    echo
    if ! test_ews_ntlm_connection; then
        print_error "NTLM-тест не пройден"
        read -p "Продолжить несмотря на ошибку? [y/N]: " continue_choice
        if [[ ! "$continue_choice" =~ ^[Yy]$ ]]; then
            print_error "Установка прервана пользователем"
            exit 1
        fi
    fi
    echo
    
    # Test LLM connectivity
    print_info "Testing LLM endpoint..."
    if check_connectivity "$LLM_ENDPOINT" 10; then
        print_success "LLM endpoint reachable"
    else
        print_error "LLM endpoint not reachable"
        print_warning "This might be normal if the endpoint requires authentication"
    fi
    
    # Check/create directories
    print_info "Checking directories..."
    local state_dir="$DIGEST_CORE_DIR/.state"
    local out_dir="$DIGEST_CORE_DIR/out"
    
    mkdir -p "$state_dir" "$out_dir"
    print_success "Directories created/verified"
}

generate_env_file() {
    print_step "Generating .env File"
    
    local env_file="$PROJECT_ROOT/.env"
    
    cat > "$env_file" << EOF
# SummaryLLM Environment Variables
# Generated by setup.sh on $(date)

# EWS Configuration
EWS_PASSWORD="$EWS_PASSWORD"
EWS_USER_UPN="$EWS_USER_UPN"
EWS_LOGIN="$EWS_LOGIN"
EWS_DOMAIN="$EWS_DOMAIN"
EWS_ENDPOINT="$EWS_ENDPOINT"

# LLM Configuration
LLM_TOKEN="$LLM_TOKEN"
LLM_ENDPOINT="$LLM_ENDPOINT"
EOF
    
    print_success ".env file created: $env_file"
}

generate_config_yaml() {
    print_step "Generating config.yaml"
    
    local config_file="$DIGEST_CORE_DIR/configs/config.yaml"
    
    # Ensure configs directory exists
    mkdir -p "$DIGEST_CORE_DIR/configs"
    
    cat > "$config_file" << EOF
# SummaryLLM Configuration
# Generated by setup.sh on $(date)

time:
  user_timezone: "$TIMEZONE"
  window: "$WINDOW_TYPE"

ews:
  endpoint: "$EWS_ENDPOINT"
  user_upn: "$EWS_USER_UPN"
  user_login: "$EWS_LOGIN"
  user_domain: "$EWS_DOMAIN"
  password_env: "EWS_PASSWORD"
  verify_ca: "$EWS_CA_CERT"
  autodiscover: false
  folders: ["$EWS_FOLDERS"]
  lookback_hours: $EWS_LOOKBACK_HOURS
  page_size: $PAGE_SIZE
  sync_state_path: "$SYNC_STATE_PATH"

llm:
  endpoint: "$LLM_ENDPOINT"
  model: "$LLM_MODEL"
  timeout_s: $LLM_TIMEOUT
  headers:
    Authorization: "Bearer \${LLM_TOKEN}"
  max_tokens_per_run: $LLM_MAX_TOKENS
  cost_limit_per_run: $COST_LIMIT

observability:
  prometheus_port: $PROMETHEUS_PORT
  log_level: "$LOG_LEVEL"
EOF
    
    print_success "config.yaml created: $config_file"
}

show_summary() {
    print_step "Configuration Summary"
    
    echo
    print_header "Configuration Files Created:"
    print_success ".env → $PROJECT_ROOT/.env"
    print_success "config.yaml → $DIGEST_CORE_DIR/configs/config.yaml"
    
    if [[ "$ENV_BACKED_UP" == "true" ]]; then
        print_info "Previous .env backed up with timestamp: $TIMESTAMP"
    fi
    
    if [[ "$CONFIG_BACKED_UP" == "true" ]]; then
        print_info "Previous config.yaml backed up with timestamp: $TIMESTAMP"
    fi
    
    echo
    print_header "Next Steps:"
    echo "1. Активировать виртуальное окружение:"
    echo "   source digest-core/.venv/bin/activate"
    echo "2. Или использовать напрямую:"
    echo "   digest-core/.venv/bin/python -m digest_core.cli run --dry-run"
    echo "3. Загрузить переменные окружения:"
    echo "   source .env"
    echo "4. Запустить тестовый прогон:"
    echo "   cd digest-core"
    echo "   .venv/bin/python -m digest_core.cli run --dry-run"
    echo "5. Запустить полный дайджест:"
    echo "   cd digest-core"
    echo "   .venv/bin/python -m digest_core.cli run"
    
    echo
    echo -n "Установить Python зависимости сейчас? [y/N]: "
    read install_deps
    if [[ "$install_deps" =~ ^[Yy]$ ]]; then
        print_info "Установка Python зависимостей в venv..."
        cd "$DIGEST_CORE_DIR"
        
        local venv_path="$DIGEST_CORE_DIR/.venv"
        if [[ ! -d "$venv_path" ]]; then
            print_error "Виртуальное окружение не найдено"
            exit 1
        fi
        
        # Установить зависимости в venv
        print_info "Установка зависимостей через pip..."
        
        # Попытка 1: стандартная установка
        if "$venv_path/bin/pip" install -e . 2>/dev/null; then
            print_success "Зависимости установлены успешно"
        elif "$venv_path/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .; then
            print_success "Зависимости установлены (с --trusted-host для корпоративных сертификатов)"
        else
            print_error "Ошибка установки зависимостей"
            print_info "Попробуйте вручную с корпоративными сертификатами:"
            echo "  cd $DIGEST_CORE_DIR"
            echo "  source .venv/bin/activate"
            echo "  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e ."
        fi
    fi
    
    echo
    print_success "Setup completed successfully! 🎉"
}

# Main function
main() {
    # Welcome message
    echo
    print_header "🚀 SummaryLLM Interactive Setup"
    echo "========================================"
    echo
    
    # Check if running in correct directory
    if [[ "$VERBOSE" == "true" ]]; then
        echo "DEBUG: SCRIPT_DIR=$SCRIPT_DIR"
        echo "DEBUG: PROJECT_ROOT=$PROJECT_ROOT"
        echo "DEBUG: DIGEST_CORE_DIR=$DIGEST_CORE_DIR"
        echo "DEBUG: Current directory: $(pwd)"
        echo "DEBUG: digest-core exists: $([[ -d "$DIGEST_CORE_DIR" ]] && echo "YES" || echo "NO")"
    fi
    
    if [[ ! -d "$DIGEST_CORE_DIR" ]]; then
        print_error "digest-core directory not found. Please run this script from the SummaryLLM root directory."
        print_error "Expected: $DIGEST_CORE_DIR"
        print_error "Current directory: $(pwd)"
        exit 1
    fi
    
    # Run setup steps
    check_dependencies
    setup_venv
    backup_configs
    collect_ews_config
    collect_llm_config
    collect_time_config
    collect_observability_config
    collect_advanced_config
    validate_connectivity
    generate_env_file
    generate_config_yaml
    show_summary
}

# Run main function
main "$@"
