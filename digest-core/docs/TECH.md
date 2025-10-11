# (Технические детали, контракты, промпты, метрики)

## 1) Стек и рантайм

- **Python 3.11**, `typer` (CLI), `httpx` (HTTP), `exchangelib` (EWS), `pydantic(v2)`, `pydantic-settings`, `tenacity`, `structlog`, `prometheus-client`.
    
- Стиль: `ruff+black+isort`, частичная `mypy` на моделях.
    

## 2) Конфигурация (пример ключей)

```yaml
ews:
  endpoint: "https://<ews-host>/EWS/Exchange.asmx"
  user_upn: "user@corp"
  password_env: "EWS_PASSWORD"
  verify_ca: "/etc/ssl/corp-ca.pem"
  autodiscover: false
  folders: ["Inbox"]
  lookback_hours: 24
  page_size: 100
  sync_state_path: ".state/ews.syncstate"

llm:
  endpoint: "https://llm-gw.corp/api/v1/chat"
  model: "corp/gpt-4o-mini"
  timeout_s: 45
  headers:
    Authorization: "Bearer ${LLM_TOKEN}"
observability:
  prometheus_port: 9108
  log_level: "INFO"
```

## 3) Нормализация писем (минимум)

- Поля: `msg_id`, `conversation_id`, `datetime_received` (UTC ISO), `sender.email`, `subject`, `text_body`.
    
- HTML→текст: удаляем `<style>`, трекинги/подписи, корректно режем цитаты (`>`, `-----Original Message-----`, `От:`/`From:`).
    
- Маскирование: email/телефоны/ФИО/ID — заменяем на `[[REDACT:TYPE]]` **до** отправки в LLM.
    

## 4) Схема JSON (контракт LLM)

```json
{
  "digest_date": "YYYY-MM-DD",
  "trace_id": "string",
  "sections": [
    {
      "title": "Мои действия",
      "items": [
        {
          "title": "string",
          "owners_masked": ["[[REDACT:...]]"],
          "due": "YYYY-MM-DD|null",
          "evidence_id": "string",
          "confidence": 0.0,
          "source_ref": {"type":"email","msg_id":"string"}
        }
      ]
    }
  ]
}
```

- Валидация pydantic на каждом запуске. Любая нестыковка → ретрай LLM с жёсткой инструкцией.
    

## 5) LLM Gateway — контракт запроса

- `POST {endpoint}` с `{model, messages:[{role:"system"/"user", content:"..."}]}`.
    
- Таймаут: 45s; ретрай 1–2 раза по `read/connect timeout`, 1 раз по «invalid JSON».
    
- Логируем: `trace_id`, `status`, `latency_ms`, `tokens_in/out` (если возвращаются заголовками).
    

## 6) Промпты (версии и правила)

- Файлы `prompts/*.j2` (иммутабельны в рантайме; версионируем).
    
- **extract_actions.v1.j2** — извлекает только действия/срочность, сохраняет `[[REDACT:...]]`, отдаёт **строго JSON** по схеме (никакого текста вне JSON).
    
- **summarize.v1.j2** — собирает краткий Markdown ≤400 слов, каждый пункт с ссылкой на `evidence_id`.
    

### Системные инварианты (вставляются в оба промпта)

- Всегда возвращай **строгий JSON** (или Markdown — когда это требуемый режим).
    
- Не раскрывай `[[REDACT:...]]`.
    
- Каждый айтем обязан иметь `evidence_id` и `source_ref`.
    
- Russian locale по умолчанию; даты в ISO.
    

## 7) Идемпотентность и high-water mark

- `(user_id, digest_date)` — ключ.
    
- Окно перестроения **T-48ч**: если входные данные менялись — пересобрать.
    
- EWS `SyncState`/watermark и локальный `.state/ews.syncstate` для инкрементальной выборки.
    

## 8) Наблюдаемость (Prometheus + логи)

- Метрики:
    
    - `llm_latency_ms` (histogram), `llm_tokens_in_total`, `llm_tokens_out_total`,
        
    - `digest_build_seconds` (summary),
        
    - `emails_total{status="fetched|filtered"}`,
        
    - `runs_total{status="ok|retry|failed"}`.
        
- Логи: structlog JSON (`run_id`, `trace_id`, стадия пайплайна, счётчики); **без** тел писем/секретов.
    

## 9) Тесты/снапшоты

- `tests/test_llm_contract.py` валидирует образец `examples/digest-YYYY-MM-DD.json`.
    
- Снапшоты Markdown/JSON — фиксируем регрессию; для не-детерминизма — стабилизируем селекцию (правила + сортировки).
    
