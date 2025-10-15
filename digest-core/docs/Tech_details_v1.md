# LLM Digest Workflow — Итоговый план реализации (MVP → LVL3)

> **Цель:** ежедневно формировать краткий, проверяемый дайджест корпоративных коммуникаций (почта, MM/Slack), с **маскированием PII на уровне корпоративного LLM Gateway**.  
> **Оркестрация:** без n8n на старте — **Python + cron/systemd (в Docker)**.  
> **Выводы:** `digest-YYYY-MM-DD.md` и `digest-YYYY-MM-DD.json` с ссылками на evidence.

---

## Содержание

- [1. Архитектура и поток данных](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#1-%D0%B0%D1%80%D1%85%D0%B8%D1%82%D0%B5%D0%BA%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BF%D0%BE%D1%82%D0%BE%D0%BA-%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85)
    
- [2. Контракты и требования](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#2-%D0%BA%D0%BE%D0%BD%D1%82%D1%80%D0%B0%D0%BA%D1%82%D1%8B-%D0%B8-%D1%82%D1%80%D0%B5%D0%B1%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D1%8F)
    
- [3. Форматы данных и схемы](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#3-%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D1%8B-%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85-%D0%B8-%D1%81%D1%85%D0%B5%D0%BC%D1%8B)
    
- [4. Конфигурация и секреты](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#4-%D0%BA%D0%BE%D0%BD%D1%84%D0%B8%D0%B3%D1%83%D1%80%D0%B0%D1%86%D0%B8%D1%8F-%D0%B8-%D1%81%D0%B5%D0%BA%D1%80%D0%B5%D1%82%D1%8B)
    
- [5. Компоненты и интерфейсы](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#5-%D0%BA%D0%BE%D0%BC%D0%BF%D0%BE%D0%BD%D0%B5%D0%BD%D1%82%D1%8B-%D0%B8-%D0%B8%D0%BD%D1%82%D0%B5%D1%80%D1%84%D0%B5%D0%B9%D1%81%D1%8B)
    
- [6. Промпты и LLM-практики](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#6-%D0%BF%D1%80%D0%BE%D0%BC%D0%BF%D1%82%D1%8B-%D0%B8-llm-%D0%BF%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B8)
    
- [7. Наблюдаемость и метрики](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#7-%D0%BD%D0%B0%D0%B1%D0%BB%D1%8E%D0%B4%D0%B0%D0%B5%D0%BC%D0%BE%D1%81%D1%82%D1%8C-%D0%B8-%D0%BC%D0%B5%D1%82%D1%80%D0%B8%D0%BA%D0%B8)
    
- [8. Тестирование и качество](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#8-%D1%82%D0%B5%D1%81%D1%82%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-%D0%B8-%D0%BA%D0%B0%D1%87%D0%B5%D1%81%D1%82%D0%B2%D0%BE)
    
- [9. Сборка, деплой, расписания](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#9-%D1%81%D0%B1%D0%BE%D1%80%D0%BA%D0%B0-%D0%B4%D0%B5%D0%BF%D0%BB%D0%BE%D0%B9-%D1%80%D0%B0%D1%81%D0%BF%D0%B8%D1%81%D0%B0%D0%BD%D0%B8%D1%8F)
    
- [10. Риски и митигации](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#10-%D1%80%D0%B8%D1%81%D0%BA%D0%B8-%D0%B8-%D0%BC%D0%B8%D1%82%D0%B8%D0%B3%D0%B0%D1%86%D0%B8%D0%B8)
    
- [11. DoD (критерии приёмки) для MVP/LVL3](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#11-dod-%D0%BA%D1%80%D0%B8%D1%82%D0%B5%D1%80%D0%B8%D0%B8-%D0%BF%D1%80%D0%B8%D1%91%D0%BC%D0%BA%D0%B8-%D0%B4%D0%BB%D1%8F-mvplvl3)
    
- [12. Roadmap до LVL3](https://chatgpt.com/g/g-p-68ea2e33e7b48191b3a54914050e0433-llm-summary-workflow/c/68ea2f46-36ec-832c-ad9c-d2590c174d0a#12-roadmap-%D0%B4%D0%BE-lvl3)
    

---

## 1. Архитектура и поток данных

**Слои:**

1. **Ingest**: EWS/IMAP (почта), Mattermost/Slack (опционально LVL3).
    
2. **Normalize**: очистка HTML, удаление цитат/подписей, унификация в `Message`.
    
3. **Threading/Dedup**: устойчивый `thread_key`, хэши контента, near-dup.
    
4. **Evidence Split**: нарезка на фрагменты 256–512 токенов, индексация.
    
5. **Context Diet**: отбор релевантных фрагментов (эмбеддинги/правила) **до шлюза**.
    
6. **LLM Gateway**: генерация структурных карточек/саммари на **замаскированном** контенте.
    
7. **Assemble**: сборка Markdown/JSON с evidence-ссылками и `[[REDACT:...]]`.
    
8. **Deliver**: отправка в MM DM/почту; публикация файлов в S3/шару.
    

**Поток (MVP):**

```
EWS -> normalize -> thread/dedup -> evidence split -> context diet
   -> LLM Gateway (masking=strict) -> structured JSON -> assemble (md/json)
   -> store (S3/disk) -> deliver (MM/Email)
```

---

## 2. Контракты и требования

**LLM Gateway (обязательные условия):**

- Маскирование PII до инференса; стабильный формат тега, напр. `[[REDACT:type=EMAIL;id=2a7c]]`.
    
- Заголовки: `x-redaction-policy: strict`, `x-log-retention: none`, `x-region`, `x-trace-id`.
    
- Возврат usage (tokens), latency, trace_id. Без логирования payload на стороне провайдера.
    

**Функциональные:**

- Дайджест за день (MVP) и период (позже) по часам.
    
- Карточки «Что важно/Срочно/Мои действия/Упоминания».
    
- Каждая карточка содержит **evidence_id** → ссылка на фрагмент источника.
    

**Нефункциональные:**

- Повторяемость: idempotency по `(user_id, date)`.
    
- Наблюдаемость: метрики + структурные логи.
    
- Приватность: хранение **только** замаскированных артефактов LLM. Сырьё писем — локальный кэш ≤ 7 дней (forensics).
    

---

## 3. Форматы данных и схемы

**3.1 `Message` (normalized JSONL/Parquet)**

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

**3.2 Evidence Split**

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

**3.3 LLM Output (структура после шлюза)**

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

**3.4 Финальные артефакты**

- `digest-YYYY-MM-DD.json` — строго по схеме (Pydantic).
    
- `digest-YYYY-MM-DD.md` — human-readable, с «Источник: письмо/канал, evidence №».
    

---

## 4. Конфигурация и секреты

`configs/config.example.yaml`

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
  model: corp/Qwen/Qwen3-30B-A3B-Instruct-2507
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

---

## 5. Компоненты и интерфейсы

**Структура репозитория**

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

**CLI (Typer)**

```python
# src/digest_core/cli.py
import typer
from digest_core.run import run_digest
app = typer.Typer()

@app.command()
def run(from_date: str = "today", sources: str = "ews",
        out: str = "./out", model: str = "corp/Qwen/Qwen3-30B-A3B-Instruct-2507"):
    run_digest(from_date, sources.split(","), out, model)

if __name__ == "__main__":
    app()
```

**LLM Gateway Client (httpx)**

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

**Pydantic-схемы**

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

---

## 6. Промпты и LLM-практики

**Общие правила промптов:**

- Требуем **строго структурный** JSON (валидируется Pydantic); автоповтор при невалидности.
    
- **Не изменять метки** `[[REDACT:...]]`; использовать их как значения в выводе.
    
- Каждый элемент должен иметь `evidence_id` (id фрагмента).
    

**Шаблон (фрагмент) `extract_actions.v1.j2`:**

```
Суммируй только действия, требующие реакции адресата.
Если встречаются метки [[REDACT:...]], сохраняй их как есть.
Верни JSON по схеме:
{ "sections": [ { "title": "Мои действия", "items": [ ... ] } ] }
Каждый item обязан иметь "evidence_id" и "confidence" ∈ [0,1].
```

---

## 7. Наблюдаемость и метрики

**Логи:** `structlog` в JSON, единый `run_id` и `trace_id`.  
**Метрики (Prometheus):**

- `emails_total`, `threads_total`, `evidence_spans_total`
    
- `llm_tokens_in`, `llm_tokens_out`, `llm_latency_ms`
    
- `digest_build_seconds`, `deliver_success_total`, `masking_errors_total`
    

Экспортёр поднимается в процессе (`observability/metrics.py`), порт из `config`.

---

## 8. Тестирование и качество

**Набор тестов:**

- `pytest` + `pytest-snapshot` для Markdown/JSON (стабильность формата).
    
- Контракт с шлюзом: мок-ответы (успех, невалидный JSON, timeout).
    
- Leakage-тесты (регулярки на email/phone/card) — **на выходах и логах**.
    
- Invariance-тесты: сравнение смысла до/после маскирования — семантическая близость (LVL3).
    

**Pre-commit:**

- `ruff`, `black`, `isort`, `mypy` (минимум на моделях), `detect-secrets`, `bandit`.
    

---

## 9. Сборка, деплой, расписания

**Dockerfile (multi-stage, slim)**

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

**Cron (host)**

```
# Ежедневно 07:30
30 7 * * * docker run --rm \
  -e EWS_USER=... -e EWS_PASSWORD=... \
  -v /opt/digest/out:/data/out corp/digest-core:latest
```

---

## 10. Риски и митигации

|Риск|Митигация|
|---|---|
|Маскирование ломает смысл|Context diet + invariance-тесты, порог confidence|
|Формат тегов шлюза меняется|Версионированный контракт + интеграционный тест|
|Утечки через логи|`log_payloads=false`, review pre-commit, e2e leakage-тест|
|Стоимость/квоты LLM|Хард-лимиты токенов, агрессивный отбор evidence, fallback|
|Хрупкость треддинга|Комбинация `In-Reply-To/References` + subject нормализация + эвристики|
|Сбої EWS/сетевые|`tenacity` ретраи, watermark/idempotency, алерты|

---

## 11. DoD (критерии приёмки) для MVP/LVL3

**MVP:**

-  CLI собирает дайджест за день из EWS, пишет `*.md` и `*.json`.
    
-  В каждом item есть `evidence_id`, в MD — ссылка «Источник».
    
-  Метрики/логи доступны; утечек PII в артефактах и логах нет.
    
-  Повторный запуск за ту же дату не дублирует вывод (idempotency).
    
-  Конфиги валидируются, секреты не пишутся в логи.
    

**LVL3 (расширение):**

-  Интеграция MM (ingest + DM-доставка), эмбеддинги + faiss для context diet.
    
-  Тесты invariance (до/после маскинга) и отчёт по качеству (faithfulness).
    
-  Параметры модели/промптов версионируются и отражаются в отчёте.
    

---

## 12. Roadmap до LVL3

1. **Неделя 1:** скелет `digest-core`, EWS ingest, normalize, assemble MD/JSON, базовые метрики.
    
2. **Неделя 2:** LLM Gateway клиент, промпты v1, контрактные тесты, leakage-тесты, Docker + cron.
    
3. **Неделя 3:** Evidence Split + context diet (правила), улучшения треддинга, снапшоты MD.
    
4. **Неделя 4 (LVL3 start):** эмбеддинги + faiss, MM ingest/deliver, invariance suite, отчёт о качестве.
    

---

## Приложение A — Минимальный `Makefile`

```makefile
.PHONY: setup test run docker

setup:
\tuv venv && uv pip install -e .[dev]

test:
\tpytest -q

run:
\tpython -m digest_core.cli run --from_date today --sources ews --out ./out

docker:
\tdocker build -t corp/digest-core:latest -f docker/Dockerfile .
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