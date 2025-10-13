#!/bin/bash
# Скрипт для тестирования подключения к EWS

echo "=== Тест подключения к EWS ==="
echo ""

# Проверяем переменные окружения
echo "Проверка переменных окружения..."
if [[ -z "$EWS_PASSWORD" ]]; then
    echo "✗ EWS_PASSWORD не установлен"
    echo "Запустите: source scripts/setup-env.sh"
    exit 1
fi

if [[ -z "$EWS_USER_UPN" ]]; then
    echo "✗ EWS_USER_UPN не установлен"
    echo "Запустите: source scripts/setup-env.sh"
    exit 1
fi

echo "✓ Переменные окружения установлены"

# Проверяем конфигурацию
echo ""
echo "Проверка конфигурации..."
cd "$(dirname "$0")/.."

if python3 -c "from src.digest_core.config import Config; config = Config(); print('✓ Конфигурация загружена')" 2>/dev/null; then
    echo "✓ Конфигурация корректна"
else
    echo "✗ Ошибка в конфигурации"
    exit 1
fi

# Тестируем инициализацию EWS модуля
echo ""
echo "Тестирование EWS модуля..."
if python3 -c "
from src.digest_core.ingest.ews import EWSIngest
from src.digest_core.config import Config
import os

# Устанавливаем тестовый пароль если не установлен
if not os.getenv('EWS_PASSWORD'):
    os.environ['EWS_PASSWORD'] = 'test_password'

try:
    config = Config()
    ingester = EWSIngest(config.ews)
    print('✓ EWS модуль инициализирован успешно')
    print(f'  Endpoint: {config.ews.endpoint}')
    print(f'  Username: {config.ews.get_ntlm_username()}')
except Exception as e:
    print(f'✗ Ошибка инициализации EWS: {e}')
    exit(1)
" 2>/dev/null; then
    echo "✓ EWS модуль работает"
else
    echo "✗ Ошибка в EWS модуле"
    exit 1
fi

# Тестируем подключение к серверу (без аутентификации)
echo ""
echo "Тестирование сетевого подключения..."
if curl -s --connect-timeout 10 -o /dev/null -w "%{http_code}" "https://owa.raiffeisen.ru/EWS/Exchange.asmx" | grep -q "200\|401\|405"; then
    echo "✓ Сервер EWS доступен"
else
    echo "✗ Сервер EWS недоступен"
    exit 1
fi

echo ""
echo "=== Тест завершен успешно! ==="
echo "Приложение готово к работе."
echo ""
echo "Для запуска используйте:"
echo "  python3 -m src.digest_core.cli run --dry-run"
