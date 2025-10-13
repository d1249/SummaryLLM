#!/bin/bash
# Wrapper скрипт для запуска SummaryLLM с автоматической загрузкой конфигурации

echo "=== Запуск SummaryLLM ==="

# Переходим в директорию проекта
cd "$(dirname "$0")/.."

# Загружаем конфигурацию
echo "Загрузка конфигурации..."
if ! source scripts/load-config.sh; then
    echo "✗ Ошибка загрузки конфигурации"
    exit 1
fi

# Проверяем пароль
if [[ -z "$EWS_PASSWORD" ]]; then
    echo "⚠️  EWS_PASSWORD не установлен"
    echo "Установите пароль: export EWS_PASSWORD='your_password'"
    echo "Или запустите: source scripts/setup-env.sh"
    exit 1
fi

echo ""
echo "=== Запуск приложения ==="

# Запускаем приложение с переданными аргументами
if [[ "$1" == "--dry-run" ]]; then
    echo "Режим: сухой прогон (dry-run)"
    python3 -m src.digest_core.cli run --dry-run
elif [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Использование:"
    echo "  ./scripts/run.sh [опции]"
    echo ""
    echo "Опции:"
    echo "  --dry-run    Сухой прогон (без реального подключения)"
    echo "  --help, -h   Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  ./scripts/run.sh --dry-run"
    echo "  ./scripts/run.sh"
    echo ""
    echo "Для настройки конфигурации:"
    echo "  source scripts/setup-env.sh"
else
    echo "Режим: полный запуск"
    python3 -m src.digest_core.cli run "$@"
fi

