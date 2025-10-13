<!-- d3d99926-0f91-4ed0-b77d-6cc670d5be5a 5c1afcb7-347c-460c-a553-4fa56610f4c7 -->
# Анализ и план исправления проблем установки

## 🔍 Анализ проблем

### Проблема 1: uv не может скачать пакеты (TLS сертификаты)

```
× Failed to fetch: `https://pypi.org/simple/tenacity/`
  ╰─▶ invalid peer certificate: UnknownIssuer
```

**Причина**: Корпоративный прокси/сертификат блокирует подключение к PyPI через `uv`.

### Проблема 2: venv не создан

```
source: no such file or directory: digest-core/.venv/bin/activate
```

**Причина**: Пользователь запустил **старый** `setup.sh` (до наших изменений), который пытался использовать `uv` вместо создания venv.

### Проблема 3: Конфигурация без NTLM полей

```
Cannot determine NTLM username: user_login and user_domain not set, and user_upn is invalid
```

**Причина**: `config.yaml` был создан старой версией `setup.sh` без полей `user_login` и `user_domain`.

## ✅ Решение

### 1. Создать скрипт диагностики и исправления

Создать `scripts/fix_installation.sh` который:

1. Проверяет версию скриптов
2. Создаёт venv если отсутствует
3. Проверяет конфигурацию на наличие новых полей
4. Устанавливает зависимости в обход проблем с TLS
```bash
#!/bin/bash
# scripts/fix_installation.sh
# Диагностика и исправление проблем с установкой

set -eo pipefail

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_step() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIGEST_CORE_DIR="$PROJECT_ROOT/digest-core"

# 1. Проверка версии setup.sh
check_setup_version() {
    print_step "Проверка версии скриптов"
    
    if grep -q "setup_venv" "$SCRIPT_DIR/setup.sh"; then
        print_success "setup.sh актуальной версии (с поддержкой venv)"
    else
        print_error "setup.sh устаревшей версии"
        print_warning "Необходимо обновить репозиторий: git pull"
        return 1
    fi
    
    if grep -q "user_login" "$SCRIPT_DIR/setup.sh"; then
        print_success "setup.sh содержит NTLM поддержку"
    else
        print_error "setup.sh без NTLM полей"
        print_warning "Необходимо обновить репозиторий: git pull"
        return 1
    fi
}

# 2. Создание venv если отсутствует
create_venv() {
    print_step "Проверка виртуального окружения"
    
    local venv_path="$DIGEST_CORE_DIR/.venv"
    
    if [[ -d "$venv_path" ]] && [[ -f "$venv_path/bin/python" ]]; then
        print_success "Виртуальное окружение существует"
        return 0
    fi
    
    print_warning "Виртуальное окружение не найдено"
    print_info "Создание venv..."
    
    # Найти Python 3.11+
    local python_bin=""
    for py in python3.12 python3.11 python3; do
        if command -v "$py" >/dev/null 2>&1; then
            local version=$("$py" --version 2>&1 | awk '{print $2}')
            local major=${version%%.*}
            local minor=$(echo "$version" | cut -d. -f2)
            if [[ $major -ge 3 ]] && [[ $minor -ge 11 ]]; then
                python_bin="$py"
                break
            fi
        fi
    done
    
    if [[ -z "$python_bin" ]]; then
        print_error "Python 3.11+ не найден"
        return 1
    fi
    
    print_info "Используется: $python_bin ($($python_bin --version))"
    
    # Создать venv
    "$python_bin" -m venv "$venv_path"
    
    if [[ $? -eq 0 ]]; then
        print_success "Виртуальное окружение создано"
        
        # Обновить pip
        print_info "Обновление pip..."
        "$venv_path/bin/pip" install --upgrade pip setuptools wheel > /dev/null 2>&1
        print_success "pip обновлён"
    else
        print_error "Не удалось создать виртуальное окружение"
        return 1
    fi
}

# 3. Установка зависимостей с обходом TLS проблем
install_dependencies() {
    print_step "Установка Python зависимостей"
    
    local venv_path="$DIGEST_CORE_DIR/.venv"
    
    if [[ ! -f "$venv_path/bin/pip" ]]; then
        print_error "pip не найден в venv"
        return 1
    fi
    
    cd "$DIGEST_CORE_DIR"
    
    print_info "Установка через pip (с корпоративными сертификатами)..."
    
    # Попытка 1: Стандартная установка
    if "$venv_path/bin/pip" install -e . 2>/dev/null; then
        print_success "Зависимости установлены"
        return 0
    fi
    
    # Попытка 2: С использованием системных сертификатов
    print_warning "Стандартная установка не удалась, пробуем с системными сертификатами..."
    if "$venv_path/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e . 2>/dev/null; then
        print_success "Зависимости установлены (с --trusted-host)"
        return 0
    fi
    
    # Попытка 3: С отключением проверки SSL (не рекомендуется, но работает)
    print_warning "Пробуем с отключением проверки SSL..."
    if PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org" "$venv_path/bin/pip" install -e .; then
        print_success "Зависимости установлены"
        print_warning "Использована установка с пониженной безопасностью"
        return 0
    fi
    
    print_error "Не удалось установить зависимости"
    print_info "Попробуйте вручную:"
    echo "  cd $DIGEST_CORE_DIR"
    echo "  source .venv/bin/activate"
    echo "  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e ."
    return 1
}

# 4. Проверка конфигурации
check_config() {
    print_step "Проверка конфигурации"
    
    local config_file="$DIGEST_CORE_DIR/configs/config.yaml"
    
    if [[ ! -f "$config_file" ]]; then
        print_error "config.yaml не найден"
        print_info "Запустите: ./scripts/setup.sh"
        return 1
    fi
    
    # Проверка на наличие новых полей
    if grep -q "user_login:" "$config_file"; then
        print_success "config.yaml содержит user_login"
    else
        print_error "config.yaml устаревший (нет user_login)"
        print_warning "Необходимо пересоздать конфигурацию"
        echo "  1. Сделать резервную копию: cp configs/config.yaml configs/config.yaml.old"
        echo "  2. Запустить setup.sh заново: cd $PROJECT_ROOT && ./scripts/setup.sh"
        return 1
    fi
    
    if grep -q "user_domain:" "$config_file"; then
        print_success "config.yaml содержит user_domain"
    else
        print_error "config.yaml устаревший (нет user_domain)"
        print_warning "Необходимо пересоздать конфигурацию"
        return 1
    fi
    
    # Проверка user_upn
    local upn=$(grep "user_upn:" "$config_file" | awk '{print $2}' | tr -d '"')
    if [[ -n "$upn" ]] && [[ "$upn" != '""' ]]; then
        print_success "user_upn настроен: $upn"
    else
        print_warning "user_upn пустой или не настроен"
    fi
}

# 5. Проверка .env
check_env() {
    print_step "Проверка переменных окружения"
    
    local env_file="$PROJECT_ROOT/.env"
    
    if [[ ! -f "$env_file" ]]; then
        print_error ".env не найден"
        print_info "Запустите: ./scripts/setup.sh"
        return 1
    fi
    
    # Проверка новых переменных
    if grep -q "EWS_LOGIN=" "$env_file"; then
        print_success ".env содержит EWS_LOGIN"
    else
        print_error ".env устаревший (нет EWS_LOGIN)"
        print_warning "Необходимо пересоздать конфигурацию: ./scripts/setup.sh"
        return 1
    fi
    
    if grep -q "EWS_DOMAIN=" "$env_file"; then
        print_success ".env содержит EWS_DOMAIN"
    else
        print_error ".env устаревший (нет EWS_DOMAIN)"
        return 1
    fi
}

# Основная функция
main() {
    echo
    echo "🔧 Диагностика и исправление установки SummaryLLM"
    echo "=================================================="
    echo
    
    local has_errors=0
    
    # Проверки
    check_setup_version || has_errors=1
    create_venv || has_errors=1
    install_dependencies || has_errors=1
    check_config || has_errors=1
    check_env || has_errors=1
    
    echo
    if [[ $has_errors -eq 0 ]]; then
        print_success "Все проверки пройдены! ✓"
        echo
        print_info "Для запуска:"
        echo "  source .env"
        echo "  cd digest-core"
        echo "  source .venv/bin/activate"
        echo "  python -m digest_core.cli run --dry-run"
    else
        print_error "Обнаружены проблемы"
        echo
        print_info "Рекомендуемые действия:"
        echo "  1. Обновить репозиторий: cd $PROJECT_ROOT && git pull"
        echo "  2. Запустить setup.sh заново: ./scripts/setup.sh"
        echo "  3. При проблемах с сертификатами использовать --trusted-host при pip install"
    fi
}

main "$@"
```


### 2. Добавить в setup.sh улучшенную обработку ошибок pip

В функции `show_summary()` добавить fallback для корпоративных сертификатов:

```bash
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
```

### 3. Добавить инструкции в README

Добавить секцию "Troubleshooting Installation" в README.md:

````markdown
## Устранение проблем при установке

### Ошибки TLS/SSL сертификатов

Если при установке возникает ошибка `invalid peer certificate: UnknownIssuer`:

```bash
# Используйте trusted-host для обхода проблем с корпоративными сертификатами
cd digest-core
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .
````

### Отсутствует venv

Если виртуальное окружение не создано:

```bash
# Запустите скрипт диагностики
./scripts/fix_installation.sh

# Или создайте вручную
cd digest-core
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### Устаревшая конфигурация

Если получаете ошибку `Cannot determine NTLM username`:

```bash
# Обновите репозиторий
git pull

# Пересоздайте конфигурацию
./scripts/setup.sh
```

```

### 4. Обновить install.sh аналогично

Добавить fallback для TLS в `install_python_deps()`:

```bash
# Установить зависимости
print_info "Установка зависимостей через pip..."

if "$venv_path/bin/pip" install -e . 2>/dev/null; then
    print_success "Зависимости установлены в venv"
elif "$venv_path/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .; then
    print_success "Зависимости установлены (с --trusted-host)"
else
    print_error "Ошибка установки зависимостей"
fi
```

## Файлы для изменения

1. **NEW**: `scripts/fix_installation.sh` - новый скрипт диагностики и исправления
2. `scripts/setup.sh` - улучшить обработку ошибок pip с TLS
3. `scripts/install.sh` - улучшить обработку ошибок pip с TLS
4. `README.md` - добавить секцию "Troubleshooting Installation"
5. `digest-core/README.md` - добавить аналогичную секцию

## Инструкции для пользователя (немедленные)

```bash
# 1. Обновить репозиторий
cd ~/SummaryLLM  # или где находится проект
git pull

# 2. Создать venv вручную (если ещё не создан)
cd digest-core
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Установить зависимости с обходом TLS проблем
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .

# 4. Проверить что конфигурация правильная
grep "user_login" configs/config.yaml

# 5. Если user_login отсутствует - пересоздать конфигурацию
cd ..
./scripts/setup.sh
```

### To-dos

- [ ] Создать scripts/fix_installation.sh для диагностики и исправления
- [ ] Улучшить обработку ошибок pip с TLS в setup.sh
- [ ] Улучшить обработку ошибок pip с TLS в install.sh
- [ ] Добавить секцию Troubleshooting Installation в README.md
- [ ] Добавить секцию Troubleshooting в digest-core/README.md