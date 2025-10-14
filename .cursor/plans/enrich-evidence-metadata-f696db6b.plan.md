<!-- f696db6b-77ad-4218-bf20-26d7ea14cf9e e1e686fe-6fe0-4f5c-a6cc-3d8ed17348c9 -->
# Обогащение Evidence метаданными и сигналами

## 1. Расширение конфигурации

**digest-core/src/digest_core/config.py**

- Добавить в `EWSConfig`:
  - `user_aliases: List[str]` - список алиасов пользователя (разделитель: запятая/точка с запятой)
- Обновить `TimeConfig.user_timezone` дефолт на `"Europe/Moscow"`

**digest-core/configs/config.example.yaml**

- Добавить пример `user_aliases: ["alias1@corp.ru", "alias2@corp.ru"]` в секцию `ews`

## 2. Расширение модели сообщения

**digest-core/src/digest_core/ingest/ews.py**

Расширить `NormalizedMessage` (NamedTuple):

```python
class NormalizedMessage(NamedTuple):
    msg_id: str
    conversation_id: str
    datetime_received: datetime
    sender_email: str
    subject: str
    text_body: str
    to_recipients: List[str]
    cc_recipients: List[str]
    # NEW FIELDS:
    importance: str  # "Low" | "Normal" | "High"
    is_flagged: bool
    has_attachments: bool
    attachment_types: List[str]  # ["pdf", "xlsx", ...]
```

В `_normalize_message()` извлекать из EWS API:

- `msg.importance` → importance
- `msg.is_flagged` → is_flagged  
- `msg.has_attachments` → has_attachments
- `msg.attachments` → attachment_types (список расширений файлов)

## 3. Создание утилит для анализа сигналов

**digest-core/src/digest_core/evidence/signals.py** (новый файл)

Функции:

- `extract_action_verbs(text: str) -> List[str]` - найти action слова (RU/EN): "please", "пожалуйста", "нужно", "approve", "срочно", "deadline"
- `extract_dates(text: str) -> List[str]` - найти даты (DD/MM/YYYY, YYYY-MM-DD, "завтра")
- `contains_question(text: str) -> bool` - проверка наличия "?"
- `normalize_datetime_to_tz(dt: datetime, tz_name: str) -> str` - конвертация в ISO-8601 с нужным TZ

## 4. Расширение EvidenceChunk

**digest-core/src/digest_core/evidence/split.py**

Расширить `EvidenceChunk` (NamedTuple):

```python
class EvidenceChunk(NamedTuple):
    evidence_id: str
    conversation_id: str
    content: str
    source_ref: Dict[str, Any]
    token_count: int
    priority_score: float
    # NEW FIELDS:
    message_metadata: Dict[str, Any]  # from, to, cc, subject, received_at, importance, flag, attachments
    addressed_to_me: bool
    user_aliases_matched: List[str]
    signals: Dict[str, Any]  # action_verbs, dates, contains_question, sender_rank, attachments
```

В `_create_evidence_chunk()` заполнять новые поля из `message` и вызовов `signals.py`.

## 5. Обновление сборки промпта

**digest-core/src/digest_core/llm/gateway.py**

В `_prepare_evidence_text()` формировать заголовок:

```
Evidence {i} (ID: {evidence_id}, Msg: {message_id}, Thread: {conversation_id})
From: {from} | To: {to} | Cc: {cc}
Subject: {subject_trunc}
ReceivedAt: {received_at_iso} | Importance: {importance} | Flag: {flag} | HasAttachments: {types_csv}
AddressedToMe: {bool} (aliases: {aliases_list})
Signals: action_verbs=[...]; dates=[...]; contains_question={bool}; sender_rank=1; attachments=[...]
---
{chunk.content}
```

Обеспечить обработку пустых/отсутствующих полей (defaults: "N/A", "Normal", "False", "[]").

## 6. Передача конфига в pipeline

**digest-core/src/digest_core/run.py**

- В `run_digest()` передавать `config.ews` в `EvidenceSplitter` и `ContextSelector`
- Обновить сигнатуры методов для передачи `user_aliases` и `user_timezone`

## 7. Юнит-тесты

**digest-core/tests/test_evidence_enrichment.py** (новый файл)

Тесты:

- `test_extract_action_verbs_ru_en()` - проверка русских/английских action слов
- `test_extract_dates()` - проверка различных форматов дат
- `test_contains_question()` - проверка флага вопроса
- `test_prepare_evidence_text_with_metadata()` - проверка полного заголовка evidence
- `test_prepare_evidence_text_missing_fields()` - устойчивость к пустым полям
- `test_addressed_to_me_detection()` - проверка определения AddressedToMe с алиасами

## Acceptance Criteria

1. В финальном промпте перед каждым chunk.content присутствуют корректно заполненные шапки
2. Все юнит-тесты зелёные (`pytest digest-core/tests/test_evidence_enrichment.py`)
3. Нулевая деградация времени генерации >5% (замерить latency_ms до/после)

### To-dos

- [ ] Расширить config.py: добавить user_aliases в EWSConfig, изменить дефолт timezone на Moscow
- [ ] Обновить config.example.yaml с примером user_aliases
- [ ] Расширить NormalizedMessage: добавить importance, is_flagged, has_attachments, attachment_types
- [ ] Обновить _normalize_message(): извлекать новые поля из EWS API (importance, flagged, attachments)
- [ ] Создать digest_core/evidence/signals.py: extract_action_verbs, extract_dates, contains_question, normalize_datetime_to_tz
- [ ] Расширить EvidenceChunk: добавить message_metadata, addressed_to_me, user_aliases_matched, signals
- [ ] Обновить _create_evidence_chunk(): заполнять новые поля, вызывать signals.py, проверять addressed_to_me
- [ ] Обновить _prepare_evidence_text(): формировать расширенный заголовок evidence с метаданными и сигналами
- [ ] Обновить run.py: передавать config.ews в EvidenceSplitter/ContextSelector для доступа к user_aliases и timezone
- [ ] Создать test_evidence_enrichment.py: тесты на signals, prepare_evidence_text, addressed_to_me, устойчивость к пустым полям
- [ ] Прогнать полный smoke test и проверить latency_ms (деградация <5%)