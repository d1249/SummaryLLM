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
source digest-core/scripts/setup-env.sh
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
./digest-core/scripts/test-connection.sh
```

## Структура конфигурации

1. **configs/config.yaml** - Основная конфигурация (без учетных данных)
2. **Переменные окружения** - Учетные данные и чувствительная информация
3. **configs/config.example.yaml** - Пример конфигурации

Конфигурация автоматически читает переменные окружения при инициализации классов `EWSConfig` и `LLMConfig`.

## Email Cleaner: Очистка тел писем от шума

### Описание

Email Cleaner автоматически удаляет из писем:
- **Quoted replies** (цитируемые ответы: `>`, "От:", "-----Original Message-----")
- **Signatures** (подписи: "С уважением", "Best regards", "Sent from my iPhone")
- **Disclaimers** (дисклеймеры: "КОНФИДЕНЦИАЛЬНОСТЬ", "DISCLAIMER", "unsubscribe")
- **Autoresponses** (автоответы: "Out of Office", "Автоответ")

Поддерживает **RU/EN** языки. Сохраняет **offset tracking** удалённых блоков для корректного маппинга evidence spans.

### Конфигурация

```yaml
# configs/config.yaml
email_cleaner:
  # Включить/выключить очистку
  enabled: true
  
  # Сохранять ли 1-2 параграфа из top-level цитаты (для inline replies)
  keep_top_quote_head: true
  max_top_quote_paragraphs: 2
  max_top_quote_lines: 10
  
  # Безопасный лимит: макс. длина одного блока для удаления (защита от удаления всего письма)
  max_quote_removal_length: 10000
  
  # Поддерживаемые локали
  locales:
    - ru
    - en
  
  # Whitelist: паттерны, которые НЕ удаляются даже если находятся в quoted/signature области
  whitelist_patterns:
    - '\b(deadline|срок|дедлайн|до)\s+\d{1,2}[./]\d{1,2}'  # Deadlines
    - '\b(approve|одобр|согласов)'  # Approval requests
  
  # Blacklist: дополнительные паттерны для агрессивного удаления
  blacklist_patterns:
    - 'Click here to unsubscribe'
    - 'Нажмите.*отписаться'
    - 'Privacy Policy'
    - 'Политика конфиденциальности'
  
  # Отслеживать удалённые spans для offset mapping
  track_removed_spans: true
```

### Примеры использования

#### Пример 1: Стандартная конфигурация

```yaml
email_cleaner:
  enabled: true
  keep_top_quote_head: true
  max_top_quote_paragraphs: 2
```

**Результат:**
- ✅ Удаляет deep nested quotes (`> > >`)
- ✅ Сохраняет 1-2 параграфа top-level quote (inline replies)
- ✅ Удаляет signatures, disclaimers, autoresponses
- ✅ Track removed spans

#### Пример 2: Агрессивная очистка

```yaml
email_cleaner:
  enabled: true
  keep_top_quote_head: false  # Удалять ВСЕ цитаты
  blacklist_patterns:
    - 'INTERNAL USE ONLY'
    - 'Строго конфиденциально'
    - 'For internal distribution'
```

**Результат:**
- ✅ Удаляет ВСЕ цитаты (без сохранения top-level)
- ✅ Дополнительно удаляет custom patterns

#### Пример 3: Консервативная очистка

```yaml
email_cleaner:
  enabled: true
  keep_top_quote_head: true
  max_top_quote_paragraphs: 3  # Больше контекста
  whitelist_patterns:
    - '\b(deadline|срок|одобр|approve|согласов)'  # Важные слова
    - '\d{1,2}[./]\d{1,2}[./]\d{2,4}'  # Даты
```

**Результат:**
- ✅ Сохраняет до 3 параграфов quoted text
- ✅ Не удаляет блоки с важными keywords

#### Пример 4: Отключение очистки

```yaml
email_cleaner:
  enabled: false
```

**Результат:**
- ❌ Очистка не применяется, письма обрабатываются «как есть»

### Метрики Prometheus

Email Cleaner экспортирует метрики для мониторинга:

```prometheus
# Количество удалённых символов по типу
email_cleaner_removed_chars_total{removal_type="quoted"} 15234
email_cleaner_removed_chars_total{removal_type="signature"} 1523
email_cleaner_removed_chars_total{removal_type="disclaimer"} 892
email_cleaner_removed_chars_total{removal_type="autoresponse"} 456

# Количество удалённых блоков по типу
email_cleaner_removed_blocks_total{removal_type="quoted"} 42
email_cleaner_removed_blocks_total{removal_type="signature"} 18
email_cleaner_removed_blocks_total{removal_type="disclaimer"} 9
email_cleaner_removed_blocks_total{removal_type="autoresponse"} 3

# Ошибки очистки
cleaner_errors_total{error_type="regex_error"} 0
cleaner_errors_total{error_type="parse_error"} 0
```

**Мониторинг:**
```bash
# Процент удалённого текста (средний)
rate(email_cleaner_removed_chars_total[5m]) / rate(emails_total[5m])

# Типичный removal rate для reply-heavy: 40-60%
```

### DoD (Definition of Done) тесты

Email Cleaner соответствует DoD требованиям:

```bash
cd digest-core
pytest tests/test_email_cleaner.py -v
```

**Критерии качества:**
- ✅ **Precision ≥ 0.95** (корректно удаляет без false positives)
- ✅ **Recall ≥ 0.90** (находит 90%+ quoted/signature/disclaimer блоков)
- ✅ **Removal rate ≥ 40%** на reply-heavy кейсах
- ✅ **Span tracking** корректен (offset validation)

### API для разработчиков

```python
from digest_core.normalize.quotes import QuoteCleaner, RemovedSpan
from digest_core.config import EmailCleanerConfig

# Инициализация
config = EmailCleanerConfig(
    enabled=True,
    keep_top_quote_head=True,
    max_top_quote_paragraphs=2
)
cleaner = QuoteCleaner(config=config)

# Очистка с span tracking
email_text = """Привет!

Согласен.

> От: Иван
> Предлагаю встретиться завтра."""

cleaned_text, removed_spans = cleaner.clean_email_body(
    text=email_text,
    lang="auto",  # или "ru", "en"
    policy="standard"  # или "aggressive", "conservative"
)

# Результат
print(f"Original: {len(email_text)} chars")
print(f"Cleaned: {len(cleaned_text)} chars")
print(f"Removed {len(removed_spans)} blocks:")

for span in removed_spans:
    print(f"  - Type: {span.type}")
    print(f"    Offset: {span.start}:{span.end}")
    print(f"    Content: {span.content[:50]}...")
    print(f"    Confidence: {span.confidence}")
```

### Troubleshooting

**Проблема:** Удаляется слишком много текста

**Решение:**
```yaml
email_cleaner:
  keep_top_quote_head: true
  max_top_quote_paragraphs: 3  # Увеличить
  whitelist_patterns:
    - 'важные_keywords'  # Добавить whitelist
```

**Проблема:** Не удаляются специфичные disclaimers

**Решение:**
```yaml
email_cleaner:
  blacklist_patterns:
    - 'Your custom disclaimer pattern'
    - 'Ваш кастомный паттерн'
```

**Проблема:** Ошибки regex в blacklist_patterns

**Решение:** Проверить синтаксис regex, экранировать спецсимволы:
```yaml
blacklist_patterns:
  - 'Price: \$\d+'  # Правильно: экранирован $
  - 'Price: $\d+'   # Неправильно: $ не экранирован
```
