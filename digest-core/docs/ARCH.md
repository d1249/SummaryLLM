# (Архитектура: C4-L2, последовательности)

## 1) Компоненты (L2)

- **CLI (Typer)** → точка входа `run_digest(from_date, sources, out, model)`.
    
- **Ingest/EWS** → `exchangelib` NTLM, без autodiscover; выборка последних X часов; нормализация.
    
- **Normalize** → HTML→текст, чистка цитат/подписей, маскирование PII.
    
- **Threads/Build** → группировка по `conversation_id`, выделение релевантных сообщений.
    
- **Evidence/Split** → разбиение длинных сообщений на куски 256–512 токенов.
    
- **Select/Context** → эвристики отбора (приоритет: запросы о действии/сроки/внешние стейкхолдеры).
    
- **LLM/Gateway** → вызов модели с промптами; валидация JSON по схеме.
    
- **Assemble** → `jsonout` (истина) и `markdown` (короткая версия).
    
- **Observability** → Prometheus-экспортер :9108, structlog.
    

## 2) Поток данных (MVP, последовательность)

1. CLI получает `from_date`, `sources="ews"`, `out`, `model`.
    
2. EWS-клиент:
    
    - Авторизация NTLM/UPN → `https://<host>/EWS/Exchange.asmx` (verify CA, no autodiscover).
        
    - **Окно выборки**: определяется как [0:00; 23:59:59] в user_timezone при режиме calendar_day; в rolling_24h — now()-24h (UTC).
        
    - Фильтр: `ReceivedTime >= window_start`, пагинация `page_size`, выбор `Inbox`.
        
    - Возвращает нормализованные записи (см. TECH 3).
        
    - **SyncState**: при ошибке выполняется безопасная реинициализация: полный прогон за `lookback_hours*3`, с дедупликацией по `msg_id` и `changekey`, после успешной сверки обновляется `SyncState`.
        
3. Normalize:
    
    - HTML→текст; убираем подписи/логотипы/трекинги; аккуратно режем цитаты.
        
    - Маскируем PII в теле/темах.
        
4. Threads/Evidence:
    
    - Группируем по `conversation_id`; отбираем последние релевантные части.
        
    - **Evidence/Split**: разрез по абзацам; если абзац >512 токенов — по предложениям; максимум 12 evidence на письмо; общий бюджет токенов на вызов LLM ≤ 3 000; при превышении — top-k по селектору важности.
        
5. Select/Context:
    
    - Простые правила: contains «пожалуйста/срок/до …», «нужно/требуется/approve», упоминания ролей, адресованные получателю.
        
    - **Фильтрация служебных писем**: Out-of-Office, Delivery Status Notification, spam-notices; признак — заголовки `Auto-Submitted`, темы `[Автоответ]`, `Undeliverable`, отправитель `postmaster@` и т. п.
        
6. LLM/Gateway:
    
    - `extract_actions.v1.j2` → строгий JSON по схеме; ретрай при невалидном JSON.
        
    - `summarize.v1.j2` → краткий md (если включено).
        
7. Assemble:
    
    - Пишем `digest-YYYY-MM-DD.json` и `.md` (≤400 слов).
        
8. Observability:
    
    - Пушим метрики; пишем структурные логи с `trace_id`.
        

## 3) Нефункциональные требования

- Надёжность: ретраи (tenacity), таймауты, фьюзы на размер батча.
    
- Производительность: страйдинг по письмам, ограничение токенов эвиденса.
    
- Безопасность: верификация корпоративного CA, секреты из ENV, отсутствие payload-логов.

## 4) Расширяемость и безопасность

- **Расширение источников**: интерфейс `SourceIngest` (plug-in) и унифицированный `source_ref` (`type`, `id`, `thread_id`). В `select/context` не шить логики, зависящей от email-полей.
    
- **Docker hardening**: контейнер запускается от non-root UID/GID; монтируется `verify_ca` read-only; переменные из `.env` не логируются; секреты через менеджер секретов (Vault/K8s Secrets); образ — distroless/slim.
    

---

# (Внутри TECH) EWS / Outlook Connect — практические детали

- **Endpoint**: `https://<ews-host>/EWS/Exchange.asmx`
    
- **Auth**: NTLM с UPN (`user@corp`), пароль из ENV. **Autodiscover = false**.
    
- **TLS**: доверие к корпоративному CA (`verify_ca`).
    
- **Папки**: `Inbox` (+ опционально `SentItems`, `Archive` при расширении).
    
- **Фильтры**: по `ReceivedTime >= now-Xh`; пагинация (Page/ItemView).
    
- **Поля**: `id/changekey`, `conversation_id`, `datetime_received`, `sender.email_address`, `to_recipients`, `cc_recipients`, `subject`, `text_body` (или аккуратный HTML→текст).
    
- **Инкрементальность**: `SyncFolderItems`/`SyncState` (локальный `.state/ews.syncstate`).
    
- **Дедуп**: по `msg_id` + `changekey` (при необходимости).
    
- **Лимиты**: ограничение вложений (MVP: игнор); защита от очень длинных тредов (обрезка/сэмплинг).
    
- **Ошибки/ретраи**: 429/5xx → экспоненциальный бэкофф; сетевые таймауты → повтор.
    