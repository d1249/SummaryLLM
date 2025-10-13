# Конфигурация SummaryLLM

## Переменные окружения

Все чувствительные данные настраиваются через переменные окружения:

### Обязательные переменные

- **EWS_ENDPOINT** - URL сервера Exchange Web Services
- **EWS_USER_UPN** - UPN пользователя (например: user@company.com)
- **EWS_PASSWORD** - Пароль пользователя

### Опциональные переменные

- **EWS_USER_LOGIN** - Логин для NTLM аутентификации (если отличается от части UPN)
- **EWS_USER_DOMAIN** - Домен для NTLM аутентификации
- **LLM_ENDPOINT** - URL сервера LLM Gateway
- **LLM_TOKEN** - Токен для доступа к LLM Gateway
- **DIGEST_CONFIG_PATH** - Путь к конфигурационному файлу

## Пример настройки

### Способ 1: Интерактивный скрипт

```bash
cd digest-core
source scripts/setup-env.sh
```

### Способ 2: Ручная настройка

```bash
export EWS_ENDPOINT="https://owa.company.com/EWS/Exchange.asmx"
export EWS_USER_UPN="user@company.com"
export EWS_USER_LOGIN="user"
export EWS_USER_DOMAIN="company.com"
export EWS_PASSWORD="your_password"
export LLM_ENDPOINT="https://llm.company.com/api"
export LLM_TOKEN="your_token"
```

### Способ 3: Файл .env

Создайте файл `.env` в корне проекта:

```bash
# EWS настройки
EWS_ENDPOINT=https://owa.company.com/EWS/Exchange.asmx
EWS_USER_UPN=user@company.com
EWS_USER_LOGIN=user
EWS_USER_DOMAIN=company.com
EWS_PASSWORD=your_password

# LLM настройки
LLM_ENDPOINT=https://llm.company.com/api
LLM_TOKEN=your_token
```

## Безопасность

- **НЕ** добавляйте реальные учетные данные в файлы конфигурации
- **НЕ** коммитьте файлы .env в репозиторий
- Используйте переменные окружения для всех чувствительных данных
- Регулярно ротируйте пароли и токены

## Проверка конфигурации

```bash
./scripts/test-connection.sh
```

## Структура конфигурации

1. **configs/config.yaml** - Основная конфигурация (без учетных данных)
2. **Переменные окружения** - Учетные данные и чувствительная информация
3. **configs/config.example.yaml** - Пример конфигурации

Конфигурация автоматически читает переменные окружения при инициализации классов `EWSConfig` и `LLMConfig`.
