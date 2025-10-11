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
        
    - Фильтр: `ReceivedTime >= now-24h`, пагинация `page_size`, выбор `Inbox`.
        
    - Возвращает нормализованные записи (см. TECH 3).
        
    - Обновляет `.state/ews.syncstate` для инкрементальной выборки.
        
3. Normalize:
    
    - HTML→текст; убираем подписи/логотипы/трекинги; аккуратно режем цитаты.
        
    - Маскируем PII в теле/темах.
        
4. Threads/Evidence:
    
    - Группируем по `conversation_id`; отбираем последние релевантные части.
        
    - Сплит на эвиденсы (256–512 токенов); назначаем `evidence_id`.
        
5. Select/Context:
    
    - Простые правила: contains «пожалуйста/срок/до …», «нужно/требуется/approve», упоминания ролей, адресованные получателю.
        
6. LLM/Gateway:
    
    - `extract_actions.v1.j2` → строгий JSON по схеме; ретрай при невалидном JSON.
        
    - `summarize.v1.j2` → краткий md (если включено).
        
7. Assemble:
    
    - Пишем `digest-YYYY-MM-DD.json` и `.md`.
        
8. Observability:
    
    - Пушим метрики; пишем структурные логи с `trace_id`.
        

## 3) Нефункциональные требования

- Надёжность: ретраи (tenacity), таймауты, фьюзы на размер батча.
    
- Производительность: страйдинг по письмам, ограничение токенов эвиденса.
    
- Безопасность: верификация корпоративного CA, секреты из ENV, отсутствие payload-логов.
    

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
    