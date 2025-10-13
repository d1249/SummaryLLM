#!/bin/bash
# Скрипт для автоматической загрузки переменных окружения из конфигурации

echo "=== Загрузка конфигурации SummaryLLM ==="

# Переходим в директорию проекта
cd "$(dirname "$0")/.."

# Проверяем наличие конфигурационного файла
CONFIG_FILE="configs/config.yaml"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "✗ Конфигурационный файл не найден: $CONFIG_FILE"
    echo "Создайте файл конфигурации или используйте setup-env.sh для интерактивной настройки"
    exit 1
fi

echo "✓ Найден конфигурационный файл: $CONFIG_FILE"

# Функция для извлечения значений из YAML
extract_yaml_value() {
    local key="$1"
    local file="$2"
    
    # Ищем значение в YAML файле
    local value=$(grep -E "^[[:space:]]*${key}:[[:space:]]*" "$file" | sed -E "s/^[[:space:]]*${key}:[[:space:]]*//" | sed 's/^"//' | sed 's/"$//')
    
    # Если значение пустое или не найдено, возвращаем пустую строку
    if [[ -z "$value" || "$value" == "null" ]]; then
        echo ""
    else
        echo "$value"
    fi
}

# Читаем значения из конфигурации
echo "Чтение конфигурации..."

EWS_ENDPOINT_CONFIG=$(extract_yaml_value "endpoint" "$CONFIG_FILE")
EWS_USER_UPN_CONFIG=$(extract_yaml_value "user_upn" "$CONFIG_FILE")
EWS_USER_LOGIN_CONFIG=$(extract_yaml_value "user_login" "$CONFIG_FILE")
EWS_USER_DOMAIN_CONFIG=$(extract_yaml_value "user_domain" "$CONFIG_FILE")

LLM_ENDPOINT_CONFIG=$(grep -A 20 "^llm:" "$CONFIG_FILE" | grep -E "^[[:space:]]*endpoint:[[:space:]]*" | sed -E "s/^[[:space:]]*endpoint:[[:space:]]*//" | sed 's/^"//' | sed 's/"$//')

# Используем значения из конфигурации или переменные окружения как fallback
EWS_ENDPOINT="${EWS_ENDPOINT_CONFIG:-$EWS_ENDPOINT}"
EWS_USER_UPN="${EWS_USER_UPN_CONFIG:-$EWS_USER_UPN}"
EWS_USER_LOGIN="${EWS_USER_LOGIN_CONFIG:-$EWS_USER_LOGIN}"
EWS_USER_DOMAIN="${EWS_USER_DOMAIN_CONFIG:-$EWS_USER_DOMAIN}"
LLM_ENDPOINT="${LLM_ENDPOINT_CONFIG:-$LLM_ENDPOINT}"

echo "✓ Конфигурация прочитана"

# Проверяем, что основные параметры EWS не пустые
if [[ -z "$EWS_ENDPOINT" || -z "$EWS_USER_UPN" ]]; then
    echo "⚠️  Основные параметры EWS не настроены в конфигурации:"
    echo "   EWS_ENDPOINT: ${EWS_ENDPOINT:-'НЕ УСТАНОВЛЕН'}"
    echo "   EWS_USER_UPN: ${EWS_USER_UPN:-'НЕ УСТАНОВЛЕН'}"
    echo ""
    echo "Для настройки запустите: source scripts/setup-env.sh"
    exit 1
fi

# Экспортируем переменные окружения
export EWS_ENDPOINT="$EWS_ENDPOINT"
export EWS_USER_UPN="$EWS_USER_UPN"

if [[ -n "$EWS_USER_LOGIN" ]]; then
    export EWS_USER_LOGIN="$EWS_USER_LOGIN"
fi

if [[ -n "$EWS_USER_DOMAIN" ]]; then
    export EWS_USER_DOMAIN="$EWS_USER_DOMAIN"
fi

if [[ -n "$LLM_ENDPOINT" ]]; then
    export LLM_ENDPOINT="$LLM_ENDPOINT"
fi

# Проверяем пароль
if [[ -z "$EWS_PASSWORD" ]]; then
    echo "⚠️  EWS_PASSWORD не установлен"
    echo "Установите пароль: export EWS_PASSWORD='your_password'"
fi

# Проверяем LLM токен
if [[ -z "$LLM_TOKEN" ]]; then
    echo "⚠️  LLM_TOKEN не установлен (опционально)"
fi

echo ""
echo "=== Переменные окружения загружены ==="
echo "EWS_ENDPOINT: $EWS_ENDPOINT"
echo "EWS_USER_UPN: $EWS_USER_UPN"
echo "EWS_USER_LOGIN: ${EWS_USER_LOGIN:-'НЕ УСТАНОВЛЕН'}"
echo "EWS_USER_DOMAIN: ${EWS_USER_DOMAIN:-'НЕ УСТАНОВЛЕН'}"
echo "LLM_ENDPOINT: ${LLM_ENDPOINT:-'НЕ УСТАНОВЛЕН'}"
echo "EWS_PASSWORD: ${EWS_PASSWORD:+[УСТАНОВЛЕН]}"
echo "LLM_TOKEN: ${LLM_TOKEN:+[УСТАНОВЛЕН]}"

echo ""
echo "=== Готово! ==="
echo "Для запуска приложения используйте:"
echo "  python3 -m src.digest_core.cli run --dry-run"
