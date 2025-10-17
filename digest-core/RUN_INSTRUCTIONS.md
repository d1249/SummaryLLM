# Инструкции по запуску SummaryLLM

## ✅ Исправления выполнены

1. **Исправлена критическая ошибка:** `AttributeError: 'EWSConfig' object has no attribute 'get_ews_password'`
2. **Настроена конфигурация:** Переменные окружения имеют приоритет над YAML
3. **Добавлены тесты:** Comprehensive unit-тесты для конфигурации

## 🚀 Правильный запуск

### Способ 1: Автоматический (рекомендуется)

```bash
# Перейдите в директорию digest-core
cd digest-core

# Запустите с автоматической загрузкой конфигурации
./digest-core/scripts/run.sh --dry-run
```

### Способ 2: Интерактивная настройка

```bash
# Перейдите в директорию digest-core
cd digest-core

# Настройте конфигурацию интерактивно
source digest-core/scripts/setup-env.sh

# Запустите приложение
./digest-core/scripts/run.sh --dry-run
```

### Способ 3: Ручная настройка

```bash
# Перейдите в директорию digest-core
cd digest-core

# Установите переменные окружения (замените на ваши данные)
export EWS_ENDPOINT="https://owa.raiffeisen.ru/EWS/Exchange.asmx"
export EWS_USER_UPN="ruapgr2@raiffeisen.ru"
export EWS_USER_LOGIN="ruapgr2"
export EWS_USER_DOMAIN="raiffeisen.ru"
export EWS_PASSWORD="ваш_реальный_пароль"

# Загрузите конфигурацию
source digest-core/scripts/load-config.sh

# Запустите приложение
python3 -m src.digest_core.cli run --dry-run
```

## 🔧 Альтернативный способ

### Использование скрипта настройки

```bash
cd digest-core
source digest-core/scripts/setup-env.sh  # Запросит данные интерактивно
python3 -m src.digest_core.cli run --dry-run
```

## 📋 Проверка исправлений

### Тест 1: Проверка конфигурации

```bash
python3 -c "
from src.digest_core.config import Config
config = Config()
print(f'Endpoint: {config.ews.endpoint}')
print(f'User: {config.ews.user_upn}')
print('✓ Конфигурация работает!')
"
```

### Тест 2: Проверка EWS модуля

```bash
python3 -c "
from src.digest_core.ingest.ews import EWSIngest
from src.digest_core.config import Config
config = Config()
ingester = EWSIngest(config.ews)
print('✓ EWS модуль работает!')
"
```

## ⚠️ Возможные проблемы

### Проблема: "Cannot determine NTLM username"
**Решение:** Убедитесь, что установлены переменные окружения:
```bash
export EWS_USER_UPN="user@domain.com"
export EWS_USER_LOGIN="user"
export EWS_USER_DOMAIN="domain.com"
```

### Проблема: "Environment variable EWS_PASSWORD not set"
**Решение:** Установите пароль:
```bash
export EWS_PASSWORD="your_password"
```

### Проблема: "AttributeError: 'EWSConfig' object has no attribute 'get_ews_password'"
**Решение:** Это означает, что исправление не применилось. Убедитесь, что:
1. Вы находитесь в правильной директории `digest-core`
2. Используете правильный Python: `python3 -m src.digest_core.cli`
3. Переменные окружения установлены

### Проблема: "SSLCertVerificationError: certificate verify failed"
**Решение:** Это проблема с SSL сертификатом сервера. В конфигурации автоматически отключена проверка SSL:
```yaml
ews:
  verify_ssl: false  # Отключает проверку SSL для самоподписанных сертификатов
```

Если нужно включить проверку SSL, установите `verify_ssl: true` и укажите путь к CA сертификату в `verify_ca`.

## 📁 Структура файлов

```
digest-core/
├── src/digest_core/
│   ├── ingest/ews.py          # ✅ Исправлен
│   └── config.py              # ✅ Обновлен
├── configs/
│   └── config.yaml            # ✅ Безопасен
├── scripts/
│   └── setup-env.sh           # ✅ Создан
└── tests/
    └── test_config.py         # ✅ Добавлен
```

## 🎯 Результат

После выполнения всех шагов приложение должно:
1. ✅ Успешно загружать конфигурацию
2. ✅ Читать переменные окружения
3. ✅ Инициализировать EWS модуль
4. ✅ Начать процесс подключения к Exchange
