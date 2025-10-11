<!-- 39bf7e9b-80cb-400a-8af3-0c7cc57ecf5e 0f078dae-1f7d-4995-929a-8135d5b96556 -->
# План анализа готовности решения digest-core к MVP

## 1. Текущее состояние решения

### Реализованная функциональность

**Основной пайплайн (полностью реализован):**

- CLI интерфейс (`cli.py`) с поддержкой dry-run режима
- EWS интеграция (`ingest/ews.py`) с NTLM аутентификацией
- Нормализация HTML в текст (`normalize/html.py`, `normalize/quotes.py`)
- Группировка по тредам (`threads/build.py`)
- Разбиение на evidence chunks (`evidence/split.py`)
- Контекстная селекция (`select/context.py`) с эвристиками
- LLM Gateway клиент (`llm/gateway.py`) с ретраями
- JSON/Markdown сборка (`assemble/jsonout.py`, `assemble/markdown.py`)
- Observability: метрики, логи, health checks (`observability/`)

**Инфраструктура:**

- Docker образ с non-root user (UID 1001)
- Prometheus метрики на :9108
- Health checks на :9109
- Makefile с командами для CI/CD
- Скрипты: test.sh, lint.sh, deploy.sh, rotate_state.sh и др.

**Документация:**

- README с примерами использования
- BRD (Business Requirements), ARCH, TECH документы
- TROUBLESHOOTING guide
- Примеры выходных артефактов

**Тестирование:**

- 98 тестов в 12 файлах
- Модули: test_cli, test_ews_ingest, test_normalize, test_llm_gateway, test_idempotency и др.
- Pydantic схемы для валидации (`llm/schemas.py`)

### Оценка соответствия BRD (DoD критериям)

**✅ Выполнено:**

- **A.** EWS загрузка с NTLM, без autodiscover ✅
- **B.** Генерация JSON (валидный по схеме) + MD (≤400 слов) ✅
- **C.** evidence_id и source_ref.msg_id в каждом айтеме ✅
- **D.** Метрики Prometheus на :9108 ✅
- **E.** Идемпотентность с окном T-48ч ✅
- **F.** Структурные логи без секретов/payload ✅

**⚠️ Частично выполнено:**

- **G.** Качество извлечения (precision ≥0.8, recall ≥0.7) - НЕ ПРОТЕСТИРОВАНО
- **H.** Обработка пустого дня - РЕАЛИЗОВАНО, но НЕ ПРОТЕСТИРОВАНО

**❌ Критические пробелы:**

- **PII политика**: Код маскирует через LLM Gateway, но нет реальной интеграции/проверки
- **Качественная оценка**: Нет ручной разметки, нет метрик качества
- **Промпты**: summarize.v1.j2 идентичен extract_actions.v1.j2 (ошибка копирования)
- **Fixtures**: tests/fixtures/emails/ пуст (0 файлов)

## 2. Критические проблемы для MVP

### 2.1. Отсутствие реальной интеграции с LLM Gateway

**Проблема:**

- `llm/gateway.py` содержит имплементацию, но нет реальной конфигурации LLM Gateway
- `config.py` загружает пароль EWS через `get_ews_password()`, но метод `get_llm_token()` вызывается из `LLMConfig` (не из `Config`)
- Нет проверки доступности LLM Gateway в health checks

**Воздействие:** Критичное - без LLM Gateway система не может функционировать

**Решение:**

- Добавить интеграционный тест с mock LLM Gateway
- Добавить health check для LLM endpoint
- Добавить .env.example с примером токена

### 2.2. Пустые test fixtures

**Проблема:**

- `tests/fixtures/emails/` пуста
- `generate_fixtures.py` не создает реальные email файлы
- Тесты работают, но без реальных email примеров

**Воздействие:** Среднее - тесты проходят, но не валидируют реальные сценарии

**Решение:**

- Сгенерировать 30+ email fixtures (HTML, plain text, кириллица, Out-of-Office, DSN)
- Обновить `generate_fixtures.py` для создания .eml/.html файлов
- Добавить fixture с длинными тредами, вложенными цитатами

### 2.3. Промпты не дифференцированы

**Проблема:**

- `prompts/extract_actions.v1.j2` и `prompts/summarize.v1.j2` идентичны
- Markdown генерация не использует правильный промпт
- Нет Jinja2 темплейтизации (файлы имеют расширение .j2, но не содержат переменных)

**Воздействие:** Высокое - Markdown выход не будет соответствовать требованиям (≤400 слов)

**Решение:**

- Переписать `summarize.v1.j2` для генерации краткого Markdown
- Добавить Jinja2 переменные: `{​{ digest_date }}`, `{​{ evidence_count }}`
- Обновить `MarkdownAssembler` для использования LLM summarization

### 2.4. Отсутствие качественных метрик

**Проблема:**

- Нет ручной разметки email выборки
- Нет метрик precision/recall для actionable items
- Нет тестов для "пустого дня" (DoD критерий H)

**Воздействие:** Критичное для production - не можем оценить качество результатов

**Решение:**

- Создать размеченную выборку ≥200 писем (actionable vs non-actionable)
- Реализовать скрипт для расчета precision/recall
- Добавить test_empty_day для валидации пустых результатов

### 2.5. Config загрузка неправильная

**Проблема:**

- `config.py` загружает только `config.example.yaml` (хардкод)
- Нет поддержки `config.yaml` (пользовательский файл)
- YAML конфиг перезаписывает ENV переменные (должно быть наоборот)

**Воздействие:** Среднее - конфигурация негибкая

**Решение:**

- Изменить порядок: ENV > config.yaml > config.example.yaml
- Добавить поддержку `DIGEST_CONFIG_PATH` env var

## 3. Задачи по категориям

### 3.1. Обязательные для MVP (блокеры)

1. **Исправить промпты** (1-2 часа)

- Переписать `summarize.v1.j2` для Markdown генерации
- Добавить Jinja2 темплейты с переменными

2. **Создать email fixtures** (2-3 часа)

- Сгенерировать 30+ email файлов (HTML, text, cyrillic, service emails)
- Обновить тесты для использования fixtures

3. **Интеграция LLM Gateway** (3-4 часа)

- Mock LLM Gateway для тестов
- Health check для LLM endpoint
- Интеграционный тест end-to-end

4. **Исправить config.py** (1 час)

- Правильный порядок загрузки: ENV > config.yaml > defaults
- Поддержка пользовательского config.yaml

5. **Тест пустого дня** (1 час)

- Реализовать test_empty_day_validation
- Проверить генерацию валидного JSON с `sections=[]`

### 3.2. Важные для Production-ready (не блокеры MVP)

6. **Качественные метрики** (1-2 дня)

- Создать размеченную выборку 200+ писем
- Реализовать скрипт для расчета precision/recall
- Документировать методологию оценки

7. **Улучшение observability** (3-4 часа)

- Добавить trace propagation в LLM Gateway
- Расширить метрики: llm_cost_estimate, email filtering stats
- Dashboard для Grafana

8. **SyncState с EWS SyncFolderItems** (4-6 часов)

- Реализовать настоящий EWS SyncFolderItems (вместо timestamp watermark)
- Обработка ошибок SyncState (reinit logic)
- Тесты для incremental sync

9. **PII Policy валидация** (2-3 часа)

- Тест для проверки [[REDACT:...]] в выходе
- Валидация, что payload не попадает в логи
- Документировать PII policy compliance

10. **CI/CD пайплайн** (3-4 часа)

- GitHub Actions / GitLab CI конфиг
- Автоматический запуск тестов на PR
- Docker image build и push

### 3.3. Желательные для улучшения (nice-to-have)

11. **Расширение тестового покрытия** (4-5 часов)

- Увеличить покрытие до ≥80% (сейчас неизвестно)
- Добавить property-based tests (hypothesis)
- Stress tests для больших объемов

12. **Документация deployment** (2-3 часа)

- Пошаговый guide для dedicated machine
- systemd service/timer примеры
- Kubernetes manifests (optional)

13. **Rotate script улучшение** (1-2 часа)

- Автоматическая архивация артефактов (ZIP + encryption)
- Retention policy enforcement (30/90 дней)

14. **Multi-user support** (1 день)

- Поддержка нескольких user_id
- Параллельная обработка (asyncio/multiprocessing)

15. **UI для просмотра дайджестов** (3-5 дней)

- Простой web UI для просмотра JSON/MD
- Фильтрация по датам, поиск

## 4. Оценка готовности по компонентам

### 4.1. Кодовая база: 75% готовности

**Готово:**

- ✅ Основной пайплайн реализован полностью
- ✅ Все модули присутствуют
- ✅ Pydantic схемы для валидации
- ✅ Observability infrastructure

**Не готово:**

- ❌ Промпты требуют исправления
- ❌ Config загрузка неправильная
- ❌ PII маскирование не валидировано

### 4.2. Тестирование: 60% готовности

**Готово:**

- ✅ 98 тестов в 12 модулях
- ✅ Unit тесты для основных модулей
- ✅ Schema validation tests

**Не готово:**

- ❌ Пустые fixtures (0 email файлов)
- ❌ Нет интеграционных тестов
- ❌ Нет качественных метрик (precision/recall)
- ❌ Coverage неизвестен

### 4.3. Документация: 80% готовности

**Готово:**

- ✅ Подробные BRD, ARCH, TECH документы
- ✅ README с примерами
- ✅ TROUBLESHOOTING guide
- ✅ Примеры артефактов

**Не готово:**

- ❌ Deployment guide для production
- ❌ Нет примеров CI/CD
- ❌ API документация (если планируется)

### 4.4. Инфраструктура: 70% готовности

**Готово:**

- ✅ Dockerfile с non-root user
- ✅ Prometheus metrics
- ✅ Health checks
- ✅ Makefile с командами

**Не готово:**

- ❌ Нет CI/CD конфигурации
- ❌ Нет Kubernetes manifests
- ❌ Нет production deployment scripts

### 4.5. Безопасность: 65% готовности

**Готово:**

- ✅ Non-root Docker container
- ✅ SSL verification с corporate CA
- ✅ Secrets через ENV

**Не готово:**

- ❌ PII policy не валидирована
- ❌ Нет security scanning (Trivy, Bandit)
- ❌ Нет secrets management (Vault)

## 5. Временные оценки

### Для достижения MVP (5 обязательных задач):

**Время:** 8-11 часов (1-1.5 рабочих дня)

### Для Production-ready (задачи 1-10):

**Время:** 3-4 рабочих дня

### Для Full-featured (задачи 1-15):

**Время:** 7-10 рабочих дней

## 6. Рекомендации

### Приоритет 1: Немедленно (для MVP)

1. Исправить промпты и config загрузку
2. Создать email fixtures
3. Добавить интеграционный тест с mock LLM
4. Протестировать пустой день

### Приоритет 2: В течение недели (для Production)

5. Качественные метрики (precision/recall)
6. CI/CD пайплайн
7. PII policy валидация
8. Улучшение observability

### Приоритет 3: Планируемое развитие

9. Multi-user support
10. UI для просмотра
11. Kubernetes deployment
12. Advanced features (attachments, календарь, etc.)

## 7. Вывод

**Текущее состояние:** Решение находится на уровне **MVP-ready 75-80%**

**Критические блокеры:**

- Промпты требуют исправления (2 часа)
- Fixtures должны быть созданы (2-3 часа)
- Config загрузка должна быть исправлена (1 час)
- LLM интеграция должна быть протестирована (3-4 часа)

**Рекомендация:** Выполнить 5 обязательных задач (1-1.5 дня работы) для запуска MVP. После этого решение будет готово для первого реального прогона с мониторингом качества.

**Для production deployment:** Добавить еще 3-4 дня на качественные метрики, CI/CD, и полноценное тестирование.