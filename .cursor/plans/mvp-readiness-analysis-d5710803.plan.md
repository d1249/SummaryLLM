<!-- d5710803-6534-4833-a5c8-b7c59003c60a 8a26e04b-d2f8-4542-9579-4d5577dcf187 -->
# План анализа готовности решения к MVP

## Обзор

Проведен комплексный анализ кодовой базы digest-core. Решение находится в состоянии **частичной готовности** (~65-70% от MVP). Основная архитектура реализована, но есть существенные пробелы в реализации, тестировании и инфраструктуре.

## 1. Статус реализации основных компонентов

### ✅ Реализовано и работает (65-70%)

#### Конфигурация и CLI

- ✅ Pydantic-based конфигурация с поддержкой YAML (`config.py`)
- ✅ Typer CLI с основными флагами (`cli.py`)
- ✅ Поддержка environment variables для секретов
- ⚠️ Флаг `--dry-run` объявлен, но не реализован

#### Ingestion (EWS)

- ✅ NTLM аутентификация через exchangelib (`ingest/ews.py`)
- ✅ Отключение autodiscover
- ✅ SSL context с корпоративным CA
- ✅ Watermark/SyncState для инкрементальной выборки
- ✅ Окна времени (calendar_day / rolling_24h)
- ✅ Базовая нормализация сообщений
- ⚠️ Отсутствует полная реализация SyncFolderItems API
- ⚠️ Нет обработки fallback при повреждении watermark
- ⚠️ Retry логика для 429/503 не полностью реализована

#### Нормализация

- ✅ HTML→текст через BeautifulSoup (`normalize/html.py`)
- ✅ Удаление inline attachments и tracking pixels
- ✅ Truncate больших тел писем (200KB)
- ✅ PII masking делегирован LLM Gateway API (по политике)
- ⚠️ `normalize/quotes.py` - не проверено содержимое
- ❌ Нет проверки denylist для утечек PII

#### Thread Building

- ✅ Группировка по conversation_id (`threads/build.py`)
- ✅ Дедупликация по msg_id
- ✅ Fallback на subject-based threading
- ✅ Лимиты: max 50 сообщений на тред
- ✅ Приоритизация тредов

#### Evidence Splitting

- ✅ Разбиение по абзацам и предложениям (`evidence/split.py`)
- ✅ Token budget: 3000 токенов на запрос
- ✅ Лимит 12 чанков на сообщение
- ✅ Оценка токенов (1.3×слова)
- ✅ Priority scoring

#### Context Selection

- ✅ Фильтрация служебных писем (`select/context.py`)
- ✅ Positive/negative signal patterns
- ✅ Direct address и deadline scoring
- ✅ Top-K selection с ограничением

#### LLM Gateway

- ✅ HTTP client с retry логикой (`llm/gateway.py`)
- ✅ JSON validation retry
- ⚠️ Quality retry частично реализован
- ✅ Token usage extraction
- ✅ Latency measurement
- ❌ Cost budget enforcement не реализован
- ❌ Rate limit handling с экспоненциальным backoff отсутствует

#### Schema & Assembly

- ✅ Pydantic схемы для Digest/Section/Item (`llm/schemas.py`)
- ✅ JSON output с валидацией (`assemble/jsonout.py`)
- ⚠️ Markdown assembly не проверен
- ✅ schema_version и prompt_version в схеме

#### Observability

- ✅ Prometheus metrics на :9108 (`observability/metrics.py`)
- ✅ Health/readiness endpoints на :9109 (`observability/healthz.py`)
- ✅ Structlog для JSON логов
- ⚠️ PII redaction в логах не реализован
- ⚠️ Метрики не проверены на высокую кардинальность

#### Идемпотентность

- ✅ T-48h rebuild window реализован в `run.py`
- ⚠️ Флаг `--force` для принудительного rebuild не реализован

### ❌ Не реализовано или требует доработки (30-35%)

#### Критические пробелы

1. **Dry-run mode** (cli.py:18-22)

- Объявлен, но возвращает "not yet implemented"
- Необходим для тестирования без LLM

2. **Quote cleaning** (normalize/quotes.py)

- Файл существует, но содержимое не проверено
- Критично для качества: удаление цитат, подписей, disclaimers

3. **PII denylist check**

- По BRD.md требуется проверка на утечку PII после обработки
- Не реализовано в нормализации

4. **LLM cost budget**

- config.llm.cost_limit_per_run объявлен, но не используется
- Нет механизма остановки при превышении

5. **LLM quality retry**

- Частично реализовано, но логика проверки "promising evidence" отсутствует

6. **Rate limit handling**

- Retry для 429/503 должен использовать jittered exponential backoff
- Текущая реализация недостаточна

7. **Markdown assembler**

- Файл `assemble/markdown.py` существует, но не проверен
- Требование: ≤400 слов, ссылки на evidence

8. **Health/readiness endpoints**

- Файл `observability/healthz.py` существует, но реализация не проверена

9. **Prompts**

- Файлы `extract_actions.v1.j2` и `summarize.v1.j2` существуют
- Содержимое не проверено на соответствие требованиям

10. **Обработка пустых дней**

- Логика для генерации валидного пустого JSON с `sections=[]` не проверена

## 2. Статус тестирования (40-50% покрытия)

### ✅ Существующие тесты (14 файлов)

Проверены 3 теста:

- ✅ `test_pii_policy.py` - корректный (проверяет делегирование PII в LLM)
- ✅ `test_ews_ingest.py` - хороший набор мокированных тестов
- ✅ `test_llm_gateway.py` - покрывает retry логику

### ❌ Пробелы в тестировании

Требуется проверить и дополнить:

1. **test_normalize.py** - проверить наличие тестов для:

- HTML→текст с кириллицей
- Удаление цитат и подписей
- Truncate на границе UTF-8
- Inline attachments и tracking pixels

2. **test_selector.py** - проверить:

- Фильтрация OOO/DSN
- Scoring heuristics
- Token budget соблюдение

3. **test_evidence_split.py** - проверить:

- Разрез по абзацам/предложениям
- Лимит 12 чанков
- Token budget 3000

4. **test_idempotency.py** - проверить:

- T-48h rebuild window
- Детерминированность при одинаковых входных данных

5. **test_markdown_json_assemble.py** - проверить:

- Markdown ≤400 слов
- Валидация JSON схемы
- Пустые дни

6. **test_observability.py** - проверить:

- /healthz и /readyz endpoints
- Метрики без высокой кардинальности

7. **test_llm_contract.py** - проверить валидацию примеров

8. **test_masking.py** - назначение неясно (возможно, дубликат test_pii_policy)

9. **test_smoke_cli.py** - проверить end-to-end тесты

### Отсутствующие тесты

- ❌ Тесты для `quotes.py`
- ❌ Тесты для `markdown.py`
- ❌ Тесты для `healthz.py`
- ❌ Интеграционные тесты с реальным EWS (опционально)
- ❌ Тесты фикстур на 30+ писем (проверить `tests/fixtures/emails/`)

## 3. Инфраструктура и скрипты

### ✅ Реализованные скрипты

- ✅ `test.sh` - pytest с coverage
- ✅ `lint.sh` - ruff + black + mypy
- ❌ Остальные 6 скриптов требуют проверки:
- `build.sh`
- `deploy.sh`
- `smoke.sh`
- `run-local.sh`
- `rotate_state.sh`
- `print_env.sh`

### ✅ Makefile

- ✅ Основные таргеты реализованы
- ✅ Таргет `ci: lint test` присутствует

### ⚠️ Docker

- ✅ Dockerfile существует и выглядит корректно
- ❌ Не проверен на сборку
- ❌ Не проверен запуск контейнера

### ❌ Systemd unit/timer

- ❌ Примеры в README, но файлы не созданы
- ❌ Требуется `examples/systemd/` директория

## 4. Документация

### ✅ Хорошо документировано

- ✅ BRD.md - полные бизнес-требования
- ✅ ARCH.md - архитектура компонентов
- ✅ TECH.md - технические детали
- ✅ README.md - хорошо структурирован

### ⚠️ Требует обновления

- README.md секции:
- PII Policy: нужно уточнить, что email НЕ маскируется локально (только в LLM Gateway)
- Diagnostics: добавить примеры разбора ошибок
- Rotation policy: уточнить 30/14/90 дней

### ❌ Отсутствует

- ❌ Changelog/Release notes
- ❌ Contributing guidelines (если планируется команда)
- ❌ Troubleshooting guide

## 5. Конфигурация

### ⚠️ Config файлы

- ✅ `configs/config.example.yaml` существует
- ❌ Содержимое не проверено на соответствие TECH.md
- ❌ `.env.example` отсутствует (упомянут в README:149)

## 6. Prompts

### ⚠️ Jinja2 templates

- ✅ `extract_actions.v1.j2` существует
- ✅ `summarize.v1.j2` существует
- ❌ Содержимое не проверено на:
- Соответствие требованиям из TECH.md:107-122
- Инструкции "Return strict JSON only"
- Сохранение `[[REDACT:...]]` markers
- Russian locale по умолчанию

## 7. Приоритетный список работ до MVP

### 🔴 Критические (блокируют MVP)

1. **Проверить и дополнить недостающие компоненты:**

- Реализовать dry-run mode
- Проверить quotes.py, markdown.py, healthz.py
- Проверить промпты на соответствие требованиям
- Проверить config.example.yaml
- Создать .env.example

2. **Дополнить критические функции:**

- PII denylist check после нормализации
- LLM cost budget enforcement
- Quality retry с проверкой promising evidence
- Rate limit exponential backoff
- Обработка пустых дней

3. **Протестировать существующие модули:**

- Запустить все 14 тестов, проверить coverage ≥70%
- Дополнить тесты для пробелов
- Добавить snapshot тесты для регрессии

4. **Проверить инфраструктуру:**

- Собрать Docker образ
- Проверить все 8 скриптов
- Smoke test end-to-end

### 🟡 Важные (улучшают качество MVP)

5. **Качество кода:**

- Запустить lint и исправить ошибки
- Добавить type hints где отсутствуют
- Code review критических путей

6. **Документация:**

- Обновить README с актуальной информацией
- Создать troubleshooting guide
- Задокументировать примеры ошибок и их решения

7. **Observability:**

- Проверить метрики на высокую кардинальность
- Добавить PII redaction в логи
- Протестировать healthz/readyz

### 🟢 Желательные (можно отложить после MVP)

8. **Расширения:**

- Примеры systemd unit/timer
- CI/CD pipeline (GitHub Actions)
- Integration tests с настоящим EWS

9. **Улучшения:**

- Более точная оценка токенов (tiktoken)
- Adaptive chunk sizing
- Более умная фильтрация служебных писем

## 8. Оценка сроков

При работе одного разработчика:

- **Критические работы (MVP-блокеры):** 3-5 дней
- **Важные работы (качество):** 2-3 дня
- **Желательные работы:** 1-2 дня

**Итого до готового MVP:** 5-8 рабочих дней

## 9. Риски

1. **EWS доступ** - требуется реальный доступ для финального тестирования
2. **LLM Gateway API** - зависимость от внешнего сервиса
3. **Качество промптов** - может потребоваться итеративная доработка
4. **Тестовые данные** - требуется выборка ≥200 писем для валидации качества (BRD.md:66)

## 10. Рекомендации

1. **Немедленно:**

- Проверить все существующие непроверенные файлы
- Запустить существующие тесты
- Собрать Docker образ

2. **В следующую очередь:**

- Дополнить критические пробелы в коде
- Довести coverage до ≥70%
- End-to-end smoke test

3. **Перед релизом:**

- Тестирование на реальном EWS
- Проверка с LLM Gateway API
- Валидация на выборке ≥200 писем

### To-dos

- [ ] Проверить содержимое непроверенных компонентов (quotes.py, markdown.py, healthz.py, prompts, config)
- [ ] Запустить все существующие тесты и проанализировать coverage
- [ ] Проверить содержимое и работоспособность 6 непроверенных скриптов
- [ ] Собрать Docker образ и проверить запуск контейнера
- [ ] Реализовать критические пробелы (dry-run, PII denylist, cost budget, rate limit)
- [ ] Дополнить тесты до coverage ≥70% и добавить snapshot тесты
- [ ] Запустить линтеры и исправить найденные проблемы
- [ ] Выполнить end-to-end smoke test с mock данными
- [ ] Обновить README и создать недостающую документацию (.env.example, troubleshooting)
- [ ] Финальная проверка на реальном EWS с LLM Gateway API (если доступно)