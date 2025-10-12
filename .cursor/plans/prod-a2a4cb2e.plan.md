<!-- a2a4cb2e-783b-4f0f-af33-b94d7e144abb 90a8a5b0-8b79-4824-bf8e-de273c706cbc -->
# План детального анализа SummaryLLM (Prod, EWS + qwen-30b)

## 1) Охват и артефакты

- Запускаем в прод-среде: реальный EWS, реальный LLM Gateway с `qwen-30b`
- Сохраняем: JSON/MD артефакты (`digest-YYYY-MM-DD.*`), метрики (:9108), health (:9109), логи (structlog), diagnostics-архив

## 2) Предварительные проверки окружения

- Проверить ENV: `EWS_USER_UPN`, `EWS_PASSWORD`, `EWS_ENDPOINT`, `LLM_TOKEN`, `LLM_ENDPOINT`
- Провалидировать `digest-core/configs/config.yaml` (модель `qwen-30b`, таймаут 60s)
- Проверить корпоративный CA (`ews.verify_ca`), доступность эндпоинтов (curl), права на каталоги `./out`, `./.state`
- Команды: `make env-check`, `python -m digest_core.cli diagnose`, `./scripts/print_env.sh`

## 3) Наблюдаемость/логирование

- Включить INFO/DEBUG в `observability.log_level`
- Убедиться, что метрики на `:9108/metrics`, health на `:9109/health`
- Сбор логов: `./scripts/collect_diagnostics.sh` (после каждого ключевого прогона)

## 4) Инжест (EWS)

- Код: `digest-core/src/digest_core/ingest/ews.py`
- Проверить окно `calendar_day` vs `rolling_24h`, пагинацию, ретраи, SyncState (`.state/ews.syncstate`)
- Измерить: emails_fetched, страницы, ошибки/ретраи, время инжеста
- Тесты: один полный день, один rolling-24h; повторный прогон для проверки идемпотентности окна

## 5) Нормализация

- Код: `normalize/html.py`, `normalize/quotes.py`
- Проверить: HTML→текст, удаление трекинга, обрезка 200KB, чистка цитат
- Сэмпловая проверка 10–20 писем (разные форматы): до/после нормализации (без логирования payload)

## 6) Треды и Evidence

- Код: `threads/build.py`, `evidence/split.py`
- Проверить группировку по `conversation_id`
- Проверить лимиты: 512 токенов/чанк, ≤12 чанков/письмо, общий бюджет ≤3000 токенов
- Зафиксировать распределения размеров, отсечки и количество выбранных кусочков

## 7) Отбор контекста

- Код: `select/context.py`
- Оценить precision/recall эвристик на реальной выборке: доля отфильтрованных сервисных писем; доля «actionable»
- Проверить ключевые паттерны (ru/en), влияние на score (адресация, дедлайны)

## 8) LLM Gateway (qwen-30b, промпты на английском)

- Код: `llm/gateway.py`, промпты: `prompts/extract_actions.en.v1.j2`, `prompts/summarize.en.v1.j2`
- Сохранить контракт: строгий JSON по схеме; заголовок секции в JSON — "Мои действия" (RU)
- Настройка: `model: qwen-30b`, `timeout_s: 60`, `temperature: 0.1`, `max_tokens: 2000`
- Проверить: строгий JSON, quality-retry при пустом ответе, обработка невалидного JSON
- Для summarize: системный промпт EN, а Markdown-вывод — RU (≤400 слов)

Мини-шаблоны промптов (EN):

```text
System (extract_actions.en.v1.j2):
You extract only actionable requests and urgent asks addressed to the recipient.
Return STRICT JSON only (no extra text) with schema:
{"sections":[{"title":"Мои действия","items":[{"title":"string","owners_masked":["list of names"],"due":"YYYY-MM-DD|null","evidence_id":"string","confidence":0.0-1.0,"source_ref":{"type":"email","msg_id":"string"}}]}]}
Ensure every item references a valid evidence_id from the user message. No other text.
```



```text

System (summarize.en.v1.j2):

You create a concise Russian Markdown digest (≤400 words) from the provided structured digest.

Headings in Russian. Every bullet references evidence_id.

If there are no actions, write: "За период релевантных действий не найдено".

```

## 9) Сборка артефактов и схема

- Код: `assemble/jsonout.py`, `assemble/markdown.py`, схема `llm/schemas.py`
- Гарантировать: валидный JSON (Pydantic), MD ≤400 слов, ссылки на `evidence_id`
- Проверить «пустой день»: пустые `sections`, корректный MD

## 10) Идемпотентность и управление артефактами

- Повторные прогоны за одну дату в пределах T-48h — артефакты не меняются
- За пределами окна — форс-пересборка
- Проверить флаг `--force` и ручное удаление артефактов

## 11) Производительность и лимиты

- Замерить энд-ту-энд время, распределение стадий (ingest/normalize/llm/assemble)
- Объем писем/день, токены in/out, стоимость на прогон (если доступно)
- Проверить пороги: timeouts, page_size, cost_limit_per_run

## 12) Безопасность/приватность

- Нет логирования payload/секретов; PII маскирование — на стороне LLM Gateway
- Проверка путей CA, переменных ENV, прав в контейнере (если Docker)

## 13) Проверка DoD (docs/reference/BRD.md)

- A–H: поставить чек-боксы с фактическими измерениями (N писем/день, метрики, идемпотентность, качество извлечения на выборке ≥200 писем)

## 14) Диагностика и отладка

- Руководство: `docs/troubleshooting/TROUBLESHOOTING.md`
- Скрипты: `./scripts/test_run.sh`, `./scripts/collect_diagnostics.sh`
- На каждый инцидент — приложить diagnostics-архив

## 15) Отчёт и рекомендации

- Сформировать краткий отчёт: метрики, несоответствия, предложения
- Если потребуется — перечислить точечные правки (паттерны контекста, бюджеты токенов, таймауты)

## Runbook (оператор на корпоративном ноутбуке)

1. Подготовка ENV и config:

   - Заполнить `.env`: `EWS_USER_UPN`, `EWS_PASSWORD`, `EWS_ENDPOINT`, `LLM_TOKEN`, `LLM_ENDPOINT`
   - В `configs/config.yaml`: `llm.model: qwen-30b`, `llm.timeout_s: 60`

2. Проверки окружения:

   - `make env-check`
   - `python -m digest_core.cli diagnose`

3. Тестовый прогон (dry-run):

   - `python -m digest_core.cli run --dry-run --from-date today --window calendar_day`

4. Полный прогон:

   - `python -m digest_core.cli run --from-date today --window calendar_day`

5. Метрики/health:

   - `curl http://localhost:9108/metrics`, `curl http://localhost:9109/health`

6. Сбор диагностики:

   - `./scripts/collect_diagnostics.sh`

## Что собрать и прислать

- `out/digest-YYYY-MM-DD.json` и `.md`
- Вывод `:9108/metrics` и `:9109/health` (тексты)
- Архив из `collect_diagnostics.sh`
- Краткие числа: emails_fetched, evidence_selected, latency_ms, tokens_in/out

## To-dos

- [ ] Провалидировать ENV, доступность EWS/LLM, CA и каталоги
- [ ] Включить метрики/логи, проверить :9108 и :9109
- [ ] Добавить английские промпты: `extract_actions.en.v1.j2`, `summarize.en.v1.j2`
- [ ] Подключить выбор промпта по модели (qwen-30b → EN)
- [ ] Прогнать calendar_day и собрать метрики инжеста
- [ ] Прогнать rolling_24h и собрать метрики
- [ ] Сделать спот-аудит нормализации на 10–20 писем
- [ ] Проверить лимиты evidence и общий бюджет токенов
- [ ] Замерить precision/recall эвристик отбора
- [ ] Прогнать qwen-30b, проверить JSON/quality-retry и метрики
- [ ] Провалидировать JSON/MD, проверить «пустой день»
- [ ] Проверить T-48h идемпотентность и флаг --force
- [ ] Собрать перф-замеры и стоимость на прогон
- [ ] Проверить отсутствие payload-логов и секретов в логах
- [ ] Заполнить чек-лист DoD A–H с фактами
- [ ] Подготовить отчёт с выводами/рекомендациями

### To-dos

- [ ] Провалидировать ENV, доступность EWS/LLM, CA и каталоги
- [ ] Включить метрики/логи, проверить :9108 и :9109
- [ ] Прогнать calendar_day и собрать метрики инжеста
- [ ] Прогнать rolling_24h и собрать метрики
- [ ] Сделать спот-аудит нормализации на 10–20 писем
- [ ] Проверить лимиты evidence и общий бюджет токенов
- [ ] Замерить precision/recall эвристик отбора
- [ ] Прогнать qwen-30b, проверить JSON/quality-retry и метрики
- [ ] Провалидировать JSON/MD, проверить «пустой день»
- [ ] Проверить T-48h идемпотентность и флаг --force
- [ ] Собрать перф-замеры и стоимость на прогон
- [ ] Проверить отсутствие payload-логов и секретов в логах
- [ ] Заполнить чек-лист DoD A–H с фактами
- [ ] Подготовить отчёт с выводами/рекомендациями