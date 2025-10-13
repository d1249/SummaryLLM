#!/bin/bash
# Скрипт для настройки переменных окружения для SummaryLLM

echo "=== Настройка переменных окружения для SummaryLLM ==="
echo ""

# Проверяем, запущен ли скрипт в интерактивном режиме
if [[ $- == *i* ]]; then
    echo "Интерактивный режим: переменные будут запрошены"
    echo ""
    
    # Запрашиваем данные для EWS
    echo -n "Введите EWS endpoint (например: https://owa.company.com/EWS/Exchange.asmx): "
    read EWS_ENDPOINT
    
    echo -n "Введите UPN пользователя (например: user@company.com): "
    read EWS_USER_UPN
    
    echo -n "Введите логин пользователя (например: user) или нажмите Enter: "
    read EWS_USER_LOGIN
    
    echo -n "Введите домен (например: company.com) или нажмите Enter: "
    read EWS_USER_DOMAIN
    
    echo -n "Введите пароль для EWS: "
    read -s EWS_PASSWORD
    echo ""
    
    # Запрашиваем токен для LLM (если есть)
    echo -n "Введите LLM токен (или нажмите Enter для пропуска): "
    read -s LLM_TOKEN
    echo ""
    
    # Запрашиваем LLM endpoint (если есть)
    echo -n "Введите LLM endpoint (или нажмите Enter для пропуска): "
    read LLM_ENDPOINT
    echo ""
else
    echo "Неинтерактивный режим: переменные должны быть установлены заранее"
    echo "Установите следующие переменные окружения:"
    echo "  export EWS_ENDPOINT='https://owa.company.com/EWS/Exchange.asmx'"
    echo "  export EWS_USER_UPN='user@company.com'"
    echo "  export EWS_USER_LOGIN='user'  # опционально"
    echo "  export EWS_USER_DOMAIN='company.com'  # опционально"
    echo "  export EWS_PASSWORD='your_password'"
    echo "  export LLM_TOKEN='your_token'  # опционально"
    echo "  export LLM_ENDPOINT='your_endpoint'  # опционально"
    echo ""
fi

# Экспортируем переменные окружения
export EWS_ENDPOINT="$EWS_ENDPOINT"
export EWS_USER_UPN="$EWS_USER_UPN"
export EWS_USER_LOGIN="$EWS_USER_LOGIN"
export EWS_USER_DOMAIN="$EWS_USER_DOMAIN"
export EWS_PASSWORD="$EWS_PASSWORD"

if [[ -n "$LLM_TOKEN" ]]; then
    export LLM_TOKEN="$LLM_TOKEN"
fi

if [[ -n "$LLM_ENDPOINT" ]]; then
    export LLM_ENDPOINT="$LLM_ENDPOINT"
fi

echo "=== Установленные переменные окружения ==="
echo "EWS_USER_UPN: $EWS_USER_UPN"
echo "EWS_ENDPOINT: $EWS_ENDPOINT"
echo "EWS_PASSWORD: [скрыто]"
if [[ -n "$LLM_TOKEN" ]]; then
    echo "LLM_TOKEN: [установлен]"
fi
if [[ -n "$LLM_ENDPOINT" ]]; then
    echo "LLM_ENDPOINT: $LLM_ENDPOINT"
fi
echo ""

# Проверяем конфигурацию
echo "=== Проверка конфигурации ==="
cd "$(dirname "$0")/.."
if [[ -f "configs/config.yaml" ]]; then
    echo "✓ Конфигурационный файл найден: configs/config.yaml"
else
    echo "✗ Конфигурационный файл не найден: configs/config.yaml"
fi

# Проверяем, что приложение может запуститься
echo ""
echo "=== Проверка приложения ==="
if python3 -c "from src.digest_core.config import Config; config = Config(); print('✓ Конфигурация загружена успешно')" 2>/dev/null; then
    echo "✓ Приложение готово к запуску"
else
    echo "✗ Ошибка при загрузке конфигурации"
    echo "Запустите диагностику: ./scripts/collect_diagnostics.sh"
fi

echo ""
echo "=== Готово! ==="
echo "Для запуска приложения используйте:"
echo "  cd digest-core"
echo "  python3 -m src.digest_core.cli run --dry-run"
