# Быстрый запуск SummaryLLM

## Исправленные проблемы

✅ **Исправлена критическая ошибка:** `AttributeError: 'EWSConfig' object has no attribute 'get_ews_password'`
- **Файл:** `src/digest_core/ingest/ews.py:65`
- **Изменение:** `self.config.get_ews_password()` → `self.config.get_password()`

## Настройка и запуск

### 1. Настройка переменных окружения

```bash
cd digest-core
source digest-core/scripts/setup-env.sh
```

Скрипт запросит:
- Пароль для EWS (`ruapgr2@raiffeisen.ru`)
- LLM токен (опционально)
- LLM endpoint (опционально)

### 2. Проверка конфигурации

```bash
./digest-core/scripts/test-connection.sh
```

### 3. Запуск приложения

```bash
# Сухой запуск (без реального подключения к EWS)
python3 -m src.digest_core.cli run --dry-run

# Полный запуск (требует реальные учетные данные)
python3 -m src.digest_core.cli run
```

## Конфигурация

Создан файл `configs/config.yaml` без реальных учетных данных.
Все чувствительные данные настраиваются через переменные окружения:

- **EWS_ENDPOINT:** URL сервера EWS
- **EWS_USER_UPN:** UPN пользователя (user@domain.com)
- **EWS_USER_LOGIN:** Логин для NTLM (опционально)
- **EWS_USER_DOMAIN:** Домен для NTLM (опционально)
- **EWS_PASSWORD:** Пароль пользователя
- **LLM_ENDPOINT:** URL сервера LLM (опционально)
- **LLM_TOKEN:** Токен для LLM (опционально)

## Тестирование

Добавлены comprehensive unit-тесты:
```bash
python3 -m pytest tests/test_config.py -v
```

## Структура исправлений

1. **Код:** Исправлен вызов метода в `ews.py:65`
2. **Тесты:** Добавлены unit-тесты для всех методов конфигурации
3. **Конфигурация:** Создана рабочая конфигурация на основе вашей curl команды
4. **Скрипты:** Созданы скрипты для настройки и тестирования

## Проверка работоспособности

Пример рабочей curl команды для тестирования EWS:
```bash
read -s EXCH_PASS; EXCH_USER='user@company.com'
curl --ntlm -u "$EXCH_USER:$EXCH_PASS" \
  -H 'Content-Type: text/xml; charset=utf-8' \
  -H 'SOAPAction: http://schemas.microsoft.com/exchange/services/2006/messages/FindItem' \
  --data @finditem.xml \
  -sS -D headers.txt -o resp.xml \
  -w '\nHTTP %{http_code}\n' \
  https://owa.company.com/EWS/Exchange.asmx
```

Приложение теперь использует переменные окружения для настройки подключения к EWS.
