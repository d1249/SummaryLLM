# SummaryLLM Implementation Guide

Детальное руководство по реализации SummaryLLM с примерами кода, архитектурными решениями и практическими рекомендациями.

## Архитектура и поток данных

### Слои системы

1. **Ingest**: EWS/IMAP (почта), Mattermost/Slack (опционально LVL3)
2. **Normalize**: очистка HTML, удаление цитат/подписей, унификация в `Message`
3. **Threading/Dedup**: устойчивый `thread_key`, хэши контента, near-dup
4. **Evidence Split**: нарезка на фрагменты 256–512 токенов, индексация
5. **Context Diet**: отбор релевантных фрагментов (эмбеддинги/правила) **до шлюза**
6. **LLM Gateway**: генерация структурных карточек/саммари на **замаскированном** контенте
7. **Assemble**: сборка Markdown/JSON с evidence-ссылками и `[[REDACT:...]]`
8. **Deliver**: отправка в MM DM/почту; публикация файлов в S3/шару

### Поток данных (MVP)

```
EWS -> normalize -> thread/dedup -> evidence split -> context diet
   -> LLM Gateway (masking=strict) -> structured JSON -> assemble (md/json)
   -> store (S3/disk) -> deliver (MM/Email)
```

## Структура репозитория

```
digest-core/
  pyproject.toml
  src/digest_core/
    cli.py               # Typer CLI
    config.py            # pydantic-settings
    ingest/ews.py
    normalize/html.py
    normalize/quotes.py
    threads/build.py
    vector/embed.py      # sentence-transformers + faiss (LVL3)
    select/context.py    # context diet
    llm/gateway.py       # httpx client (masking=strict)
    llm/schemas.py       # Pydantic output models
    assemble/markdown.py
    assemble/jsonout.py
    deliver/mm.py
    observability/logs.py
    observability/metrics.py
  prompts/
    summarize.v1.j2
    extract_actions.v1.j2
  tests/
    test_ingest_ews.py
    test_normalize.py
    test_llm_contract.py
    snapshots/
  docker/Dockerfile
  configs/config.example.yaml
  Makefile
```

## Компоненты и интерфейсы

### CLI (Typer)

```python
# src/digest_core/cli.py
import typer
from digest_core.run import run_digest

app = typer.Typer()

@app.command()
def run(from_date: str = "today", sources: str = "ews",
        out: str = "./out", model: str = "corp/gpt-4o-mini"):
    run_digest(from_date, sources.split(","), out, model)

if __name__ == "__main__":
    app()
```

### LLM Gateway Client (httpx)

```python
# src/digest_core/llm/gateway.py
import httpx, uuid, time
from typing import Dict, Any

class GatewayClient:
    def __init__(self, endpoint: str, headers: Dict[str,str], model: str, timeout_s=120):
        self.endpoint, self.headers, self.model = endpoint, headers, model
        self.timeout = httpx.Timeout(timeout_s)

    def chat(self, messages: list[dict[str, str]]) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        hdrs = {**self.headers, "x-trace-id": trace_id}
        payload = {"model": self.model, "messages": messages}
        t0 = time.perf_counter()
        with httpx.Client(timeout=self.timeout) as cli:
            r = cli.post(self.endpoint, headers=hdrs, json=payload)
        latency_ms = int(1000*(time.perf_counter()-t0))
        r.raise_for_status()
        data = r.json()
        return {"trace_id": trace_id, "latency_ms": latency_ms, "data": data}
```

### Pydantic-схемы

```python
# src/digest_core/llm/schemas.py
from pydantic import BaseModel, Field, AwareDatetime
from typing import List, Optional

class Item(BaseModel):
    title: str
    owners_masked: List[str] = Field(default_factory=list)
    due: Optional[str] = None
    evidence_id: str
    confidence: float
    source_ref: dict

class Section(BaseModel):
    title: str
    items: List[Item]

class Digest(BaseModel):
    digest_date: str
    generated_at: AwareDatetime
    trace_id: str
    sections: List[Section]
```

## Конфигурация и секреты

### configs/config.example.yaml

```yaml
ingest:
  ews:
    url: https://ews.corp/ews/exchange.asmx
    auth: ntlm
    user: ${EWS_USER}
    password: ${EWS_PASSWORD}
    mailbox: me@corp
  mattermost:
    enabled: false
    token: ${MM_TOKEN}
    base_url: https://mm.corp

llm:
  provider: gateway
  endpoint: https://llm-gw.corp/api/v1/chat
  model: corp/gpt-4o-mini
  masking: upstream_strict
  redact_tag_format: "[[REDACT:{attrs}]]"
  headers:
    x-redaction-policy: strict
    x-log-retention: none
    x-region: us-east

limits:
  max_tokens_in: 6000
  max_tokens_out: 1200
  max_evidence_spans: 10

privacy:
  cache_raw_days: 7
  store_masked_only: true

observability:
  log_json: true
  log_payloads: false
  prometheus_port: 9108

output:
  dir: /data/out
  s3:
    enabled: false
    bucket: corp-digests
```

Секреты — через ENV/ваулт. Конфиг валидируется `pydantic-settings`.

## Форматы данных и схемы

### Message (normalized JSONL/Parquet)

```json
{
  "source": "ews",
  "msg_id": "urn:ews:.../ChangeKey...",
  "thread_key": "b3e9d3...",
  "ts": "2025-10-10T08:42:11Z",
  "from": "Alice <alice@corp>",
  "to": ["Bob <bob@corp>"],
  "subject": "Q3 Budget plan",
  "body_md": "…markdown…",
  "attachments": [],
  "hash": "blake3:...",
  "flags": {"is_reply": true}
}
```

### Evidence Split

```json
{
  "evidence_id": "ev:msghash:offset:len",
  "msg_id": "…",
  "thread_key": "…",
  "offset": 1024,
  "len": 480,
  "text": "…raw fragment…"
}
```

### LLM Output (структура после шлюза)

```json
{
  "digest_date": "2025-10-10",
  "trace_id": "…",
  "sections": [
    {
      "title": "Мои действия",
      "items": [
        {
          "title": "Утвердить лимиты Q3",
          "owners_masked": ["[[REDACT:NAME;id=9b3e]]"],
          "due": "2025-10-12",
          "evidence_id": "ev:…",
          "confidence": 0.86,
          "source_ref": {"type":"email","msg_id":"…"}
        }
      ]
    }
  ]
}
```

### Финальные артефакты

- `digest-YYYY-MM-DD.json` — строго по схеме (Pydantic)
- `digest-YYYY-MM-DD.md` — human-readable, с «Источник: письмо/канал, evidence №»

## Промпты и LLM-практики

### Общие правила промптов

- Требуем **строго структурный** JSON (валидируется Pydantic); автоповтор при невалидности
- **Не изменять метки** `[[REDACT:...]]`; использовать их как значения в выводе
- Каждый элемент должен иметь `evidence_id` (id фрагмента)

### Шаблон (фрагмент) extract_actions.v1.j2

```
Суммируй только действия, требующие реакции адресата.
Если встречаются метки [[REDACT:...]], сохраняй их как есть.
Верни JSON по схеме:
{ "sections": [ { "title": "Мои действия", "items": [ ... ] } ] }
Каждый item обязан иметь "evidence_id" и "confidence" ∈ [0,1].
```

## Наблюдаемость и метрики

### Логи

`structlog` в JSON, единый `run_id` и `trace_id`

### Метрики (Prometheus)

- `emails_total`, `threads_total`, `evidence_spans_total`
- `llm_tokens_in`, `llm_tokens_out`, `llm_latency_ms`
- `digest_build_seconds`, `deliver_success_total`, `masking_errors_total`

Экспортёр поднимается в процессе (`observability/metrics.py`), порт из `config`.

## Docker

### Dockerfile (multi-stage, slim)

```dockerfile
FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv venv
COPY . .
RUN . .venv/bin/activate && uv pip install -e .

FROM python:3.11-slim
WORKDIR /app
COPY --from=base /app /app
USER 1001
EXPOSE 9108
ENTRYPOINT ["python","-m","digest_core.cli","run","--from_date","today","--sources","ews","--out","/data/out"]
```

### Cron (host)

```
# Ежедневно 07:30
30 7 * * * docker run --rm \
  -e EWS_USER=... -e EWS_PASSWORD=... \
  -v /opt/digest/out:/data/out corp/digest-core:latest
```

## Тестирование и качество

### Набор тестов

- `pytest` + `pytest-snapshot` для Markdown/JSON (стабильность формата)
- Контракт с шлюзом: мок-ответы (успех, невалидный JSON, timeout)
- Leakage-тесты (регулярки на email/phone/card) — **на выходах и логах**
- Invariance-тесты: сравнение смысла до/после маскирования — семантическая близость (LVL3)

### Pre-commit

- `ruff`, `black`, `isort`, `mypy` (минимум на моделях), `detect-secrets`, `bandit`

## Риски и митигации

| Риск | Митигация |
|------|-----------|
| Маскирование ломает смысл | Context diet + invariance-тесты, порог confidence |
| Формат тегов шлюза меняется | Версионированный контракт + интеграционный тест |
| Утечки через логи | `log_payloads=false`, review pre-commit, e2e leakage-тест |
| Стоимость/квоты LLM | Хард-лимиты токенов, агрессивный отбор evidence, fallback |
| Хрупкость треддинга | Комбинация `In-Reply-To/References` + subject нормализация + эвристики |
| Сбои EWS/сетевые | `tenacity` ретраи, watermark/idempotency, алерты |

## DoD (критерии приёмки) для MVP/LVL3

### MVP

- CLI собирает дайджест за день из EWS, пишет `*.md` и `*.json`
- В каждом item есть `evidence_id`, в MD — ссылка «Источник»
- Метрики/логи доступны; утечек PII в артефактах и логах нет
- Повторный запуск за ту же дату не дублирует вывод (idempotency)
- Конфиги валидируются, секреты не пишутся в логи

### LVL3 (расширение)

- Интеграция MM (ingest + DM-доставка), эмбеддинги + faiss для context diet
- Тесты invariance (до/после маскинга) и отчёт по качеству (faithfulness)
- Параметры модели/промптов версионируются и отражаются в отчёте

## Roadmap до LVL3

1. **Неделя 1:** скелет `digest-core`, EWS ingest, normalize, assemble MD/JSON, базовые метрики
2. **Неделя 2:** LLM Gateway клиент, промпты v1, контрактные тесты, leakage-тесты, Docker + cron
3. **Неделя 3:** Evidence Split + context diet (правила), улучшения треддинга, снапшоты MD
4. **Неделя 4 (LVL3 start):** эмбеддинги + faiss, MM ingest/deliver, invariance suite, отчёт о качестве

## Приложение A — Минимальный Makefile

```makefile
.PHONY: setup test run docker

setup:
	uv venv && uv pip install -e .[dev]

test:
	pytest -q

run:
	python -m digest_core.cli run --from_date today --sources ews --out ./out

docker:
	docker build -t corp/digest-core:latest -f docker/Dockerfile .
```

## Приложение B — Пример Markdown-выхода (фрагмент)

```md
# Дайджест — 2025-10-10

## Мои действия
- Утвердить лимиты Q3 — до **2025-10-12**. Ответственные: [[REDACT:NAME;id=9b3e]].  
  Источник: письмо «Q3 Budget plan», evidence ev:msghash:1024:480.

## Срочно
- [[REDACT:NAME;id=f1d0]] просит подтвердить SLA инцидента #7842.  
  Источник: «ADP incident update», evidence ev:...
```

---

**Итого:** у нас единый, тестируемый Python-пакет с жёсткими контрактами маскирования через корпоративный LLM Gateway, метриками/логами и воспроизводимыми артефактами. На старте — cron + Docker; расширение до LVL3 без смены ядра.
