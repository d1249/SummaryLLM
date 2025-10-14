<!-- d58a1273-b7e9-46f5-a32e-81801e02d02e c68488b8-19d7-46e9-ace8-c753162e817f -->
# Добавление статистики и тем писем в дайджест

## Изменения в схемах данных

### 1. Обновить `schemas.py`

- Добавить в `Digest` (v1) и `EnhancedDigest` (v2):
- `total_emails_processed: int` - всего обработано писем
- `emails_with_actions: int` - писем с действиями
- Добавить в `Item` (v1): `email_subject: Optional[str]` 
- Добавить в `ActionItem` (v2): `email_subject: Optional[str]`
- Добавить в `DeadlineMeeting`, `RiskBlocker`, `FYIItem`: `email_subject: Optional[str]`

### 2. Обновить `run.py` - сбор статистики

#### Для flat mode (v1):

- После получения `digest_data` от LLM подсчитать:
- `total_emails_processed = len(messages)`
- `emails_with_actions` = количество уникальных msg_id в actions
- Обогатить каждый `Item` темой письма из `evidence_chunks`
- Добавить статистику в `digest_data`

#### Для hierarchical mode (v2):

- Аналогично подсчитать статистику
- Передать `evidence_chunks` в `hierarchical_processor` для обогащения тем
- Обогатить действия темами писем

### 3. Обновить `hierarchical/processor.py`

В `_final_aggregation`:

- Принимать `all_chunks` как параметр
- После получения digest от LLM обогатить каждое действие темой из соответствующего evidence chunk
- Создать mapping `evidence_id -> subject` из chunks

### 4. Обновить `markdown.py`

#### В `_generate_markdown` (v1):

- В конце, перед секцией "Источники" добавить секцию "## Статистика"
- Показать: "Обработано {total} писем, {with_actions} ({percent}%) содержали действия"
- В строке "Источник" добавить тему: `**Источник:** {type}, тема "{subject}", evidence {evidence_id}`

#### В `_generate_enhanced_markdown` (v2):

- Аналогично добавить статистику в конец
- В строке "Источник" для всех типов действий добавить тему

### 5. Обновить `jsonout.py`

В `_digest_to_dict`:

- Добавить поля `total_emails_processed` и `emails_with_actions`
- Добавить `email_subject` для каждого item

В `_dict_to_digest`:

- Читать новые поля (с дефолтами для обратной совместимости)

### 6. Обновить `evidence/split.py`

В `_create_evidence_chunk`:

- Убедиться что `message.subject` сохраняется в `message_metadata["subject"]`
- Это уже сделано на строке 263

## Ключевые файлы для изменения

- `digest-core/src/digest_core/llm/schemas.py` - схемы данных
- `digest-core/src/digest_core/run.py` - сбор статистики
- `digest-core/src/digest_core/hierarchical/processor.py` - обогащение тем в hierarchical mode
- `digest-core/src/digest_core/assemble/markdown.py` - отображение в MD
- `digest-core/src/digest_core/assemble/jsonout.py` - JSON формат

### To-dos

- [ ] Обновить схемы Digest, EnhancedDigest, Item, ActionItem - добавить статистику и email_subject
- [ ] В run.py добавить подсчет статистики и обогащение тем для flat mode
- [ ] В run.py добавить подсчет статистики для hierarchical mode
- [ ] В hierarchical/processor.py добавить обогащение действий темами писем
- [ ] В markdown.py добавить секцию статистики и темы в строку Источник
- [ ] В jsonout.py добавить поддержку новых полей статистики и тем