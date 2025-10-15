# Action/Mention Extraction: Rule-Based My Actions

## Обзор

Система извлечения действий и упоминаний (Action/Mention Extraction) автоматически выделяет адресные просьбы и упоминания пользователя из корпоративной email-переписки.

**Ключевые особенности**:
- ✅ **Rule-based подход**: regex + эвристики (без ML/LLM)
- ✅ **Двуязычность**: RU + EN поддержка из коробки
- ✅ **Confidence scoring**: логистическая функция для ранжирования
- ✅ **Integration с citations**: каждое действие имеет трассируемые оффсеты
- ✅ **High precision**: P ≥ 0.85, R ≥ 0.80 (validated on gold set)

## Типы извлечений

### 1. **Actions** — Явные просьбы/императивы

**Примеры**:
- 🇷🇺 "Иван, пожалуйста **сделайте** отчет до завтра"
- 🇬🇧 "Ivan, **please review** the PR by Friday"

**Признаки**:
- Imperative verbs: сделай(те), review, complete, approve
- Action markers: нужно, необходимо, please, need to
- Addressability: упоминание user alias

### 2. **Questions** — Вопросы, требующие ответа

**Примеры**:
- 🇷🇺 "Иван, **когда** вы сможете проверить?"
- 🇬🇧 "**Can you** update the docs, Ivan?"

**Признаки**:
- Question markers: `?`, когда/где/как, what/when/how
- Modal verbs: can you, could you, можешь, можете

### 3. **Mentions** — Упоминания без явного действия

**Примеры**:
- 🇷🇺 "Обсудили это с **Иваном Петровым** вчера"
- 🇬🇧 "**ivan.petrov@corp.com** is aware of this"

**Признаки**:
- User alias presence
- No strong imperative/question signal

## Confidence Scoring

### Логистическая функция

```python
confidence = 1 / (1 + exp(-score + bias))

score = Σ (weight_i * feature_i)
```

### Веса признаков

| Признак | Вес | Описание |
|---------|-----|----------|
| `has_user_mention` | 1.5 | Прямое упоминание user alias |
| `has_imperative` | 1.2 | Императивный глагол |
| `has_action_marker` | 1.0 | Маркер действия (нужно, please) |
| `is_question` | 0.8 | Вопросительная конструкция |
| `has_deadline` | 0.6 | Наличие дедлайна/даты |
| `sender_rank` | 0.5 | Важность отправителя (0.0-1.0) |

### Интерпретация

- **≥ 0.85**: High confidence — точно My Action
- **0.50-0.84**: Medium confidence — вероятное действие
- **< 0.50**: Low confidence — упоминание или false positive

## Архитектура

### ActionMentionExtractor

```python
extractor = ActionMentionExtractor(
    user_aliases=["ivan.petrov@corp.com", "Иван Петров", "ivanov"],
    user_timezone="Europe/Moscow"
)

actions = extractor.extract_mentions_actions(
    text=email_body,          # Normalized text (after cleaner)
    msg_id="msg-123",
    sender="boss@corp.com",
    sender_rank=0.8           # 0.0-1.0
)
```

**Возвращает**: `List[ExtractedAction]`

### ExtractedAction Schema

```python
@dataclass
class ExtractedAction:
    type: str                 # "action", "question", "mention"
    who: str                  # "user" (for My Actions)
    verb: str                 # Action verb: "review", "approve", "answer"
    text: str                 # Full text of action/mention
    due: Optional[str]        # Deadline: "завтра", "Friday", "15.01"
    confidence: float         # 0.0-1.0
    evidence_id: str          # Evidence chunk reference
    msg_id: str               # Message ID
    start_offset: int         # Start offset in normalized text
    end_offset: int           # End offset
```

## Regex Patterns

### Russian Imperatives

```regex
\b(сделай(?:те)?|выполни(?:те)?|проверь(?:те)?|отправь(?:те)?)
\b(подготовь(?:те)?|согласуй(?:те)?|утверди(?:те)?|одобри(?:те)?)
\b(посмотри(?:те)?|изучи(?:те)?|рассмотри(?:те)?|оцени(?:те)?)
\b(ответь(?:те)?|напиши(?:те)?|сообщи(?:те)?|уведоми(?:те)?)
```

### English Imperatives

```regex
\b(please|could you|can you|would you|will you)
\b(need you to|want you to|asking you to|request you to)
\b(make sure|ensure|verify|confirm|check)
\b(review|approve|sign off|validate|examine)
\b(send|provide|submit|deliver|share)
```

### Deadline Patterns

```regex
\b(до|к|не позднее)\s+\d{1,2}[./]\d{1,2}       # до 15.01
\b(by|until|before)\s+\d{1,2}[./]\d{1,2}        # by 01/15
\b(сегодня|завтра|послезавтра)                  # today, tomorrow
\b(monday|tuesday|wednesday|thursday|friday)    # weekdays
\b(deadline|дедлайн|срок)\s*:?\s*\d            # deadline: 15.01
\b(eod|end of day|конец дня)                    # EOD
```

## Pipeline Integration

### Диаграмма потока

```
Ingest → Normalize → Clean → Threads → Evidence Split
                                            ↓
                                  4.5: Action Extraction
                                            ↓
                        ActionMentionExtractor.extract_mentions_actions()
                                            ↓
                     enrich_actions_with_evidence(actions, chunks)
                                            ↓
                             Convert to ExtractedActionItem
                                            ↓
                        enrich_item_with_citations(item, chunks)
                                            ↓
                      digest.extracted_actions.append(item)
                                            ↓
                                Sort by confidence ↓
                                            ↓
                                    Assemble JSON/MD
```

### Код в run.py

```python
# Step 4.5: Extract actions (after evidence splitting)
action_extractor = ActionMentionExtractor(
    user_aliases=config.ews.user_aliases,
    user_timezone=config.time.user_timezone
)

all_extracted_actions = []
for msg in normalized_messages:
    msg_actions = action_extractor.extract_mentions_actions(
        text=msg.text_body,
        msg_id=msg.msg_id,
        sender=msg.sender,
        sender_rank=0.5
    )
    
    # Enrich with evidence_id
    msg_actions = enrich_actions_with_evidence(msg_actions, evidence_chunks, msg.msg_id)
    
    # Record metrics
    for action in msg_actions:
        metrics.record_action_found(action.type)
        metrics.record_action_confidence(action.confidence)
        if action.type == "mention":
            metrics.record_mention_found()
    
    all_extracted_actions.extend(msg_actions)

# Step 6.6: Add to digest with citations
for action in all_extracted_actions:
    extracted_item = ExtractedActionItem(
        type=action.type,
        who=action.who,
        verb=action.verb,
        text=action.text,
        due=action.due,
        confidence=action.confidence,
        evidence_id=action.evidence_id,
        email_subject=evidence_to_subject.get(action.evidence_id, "")
    )
    
    # Enrich with citations
    enrich_item_with_citations(extracted_item, evidence_chunks, citation_builder)
    
    digest.extracted_actions.append(extracted_item)

# Sort by confidence
digest.extracted_actions.sort(key=lambda a: a.confidence, reverse=True)
```

## JSON Output

```json
{
  "schema_version": "2.0",
  "extracted_actions": [
    {
      "type": "action",
      "who": "user",
      "verb": "review",
      "text": "Иван, пожалуйста проверьте документ до завтра",
      "due": "завтра",
      "confidence": 0.92,
      "evidence_id": "ev-123",
      "citations": [
        {
          "msg_id": "msg-abc",
          "start": 45,
          "end": 95,
          "preview": "Иван, пожалуйста проверьте документ до завтра. Спасибо!"
        }
      ],
      "email_subject": "Urgent: Document Review"
    },
    {
      "type": "question",
      "who": "user",
      "verb": "answer",
      "text": "Can you provide status update on the project?",
      "due": null,
      "confidence": 0.78,
      "evidence_id": "ev-124",
      "citations": [...]
    }
  ]
}
```

## Метрики (Prometheus)

### actions_found_total

**Counter** с labels `action_type: [action, question, mention]`

```promql
# Total actions extracted
sum(actions_found_total)

# Actions by type
sum by (action_type) (actions_found_total)

# Rate of action extraction
rate(actions_found_total[5m])
```

### mentions_found_total

**Counter** для user mentions

```promql
# Total mentions
mentions_found_total

# Mentions per minute
rate(mentions_found_total[1m])
```

### actions_confidence_histogram

**Histogram** с buckets `[0.0, 0.3, 0.5, 0.7, 0.85, 0.95, 1.0]`

```promql
# Median confidence
histogram_quantile(0.5, actions_confidence_histogram)

# 90th percentile
histogram_quantile(0.9, actions_confidence_histogram)

# High-confidence actions (>= 0.85)
sum(actions_confidence_histogram_bucket{le="1.0"}) - sum(actions_confidence_histogram_bucket{le="0.85"})
```

## Precision/Recall Validation

### Gold Set

Тесты включают **Gold Set** из 18 образцов:
- ✅ 10 True Positives (должны извлекаться)
- ✅ 4 Medium cases (упоминания)
- ❌ 4 True Negatives (не должны извлекаться)

### Требования (DoD)

- **Precision ≥ 0.85**: ≥85% извлеченных действий — реальные My Actions
- **Recall ≥ 0.80**: ≥80% реальных My Actions извлечены
- **F1 ≥ 0.82**: Балансированная метрика

### Запуск валидации

```bash
cd digest-core
pytest tests/test_actions.py::TestGoldSetValidation::test_gold_set_precision_recall -v

# Expected output:
# === Gold Set Validation ===
# True Positives: 14
# False Positives: 1
# True Negatives: 3
# False Negatives: 2
# Precision: 0.933
# Recall: 0.875
# F1 Score: 0.903
# ===========================
```

## Usage Examples

### Базовое использование

```python
from digest_core.evidence.actions import ActionMentionExtractor

# Initialize
extractor = ActionMentionExtractor(
    user_aliases=["ivan.petrov@corp.com", "Иван Петров"],
    user_timezone="Europe/Moscow"
)

# Extract from email
email_text = "Иван, пожалуйста согласуйте бюджет до пятницы."
actions = extractor.extract_mentions_actions(
    text=email_text,
    msg_id="msg-001",
    sender="manager@corp.com",
    sender_rank=0.8
)

# Process results
for action in actions:
    print(f"Type: {action.type}")
    print(f"Confidence: {action.confidence:.2f}")
    print(f"Text: {action.text}")
    print(f"Deadline: {action.due}")
```

### С enrichment

```python
from digest_core.evidence.actions import enrich_actions_with_evidence

# Enrich with evidence_id
enriched = enrich_actions_with_evidence(
    actions=actions,
    evidence_chunks=all_chunks,
    msg_id="msg-001"
)

# Now actions have evidence_id set
for action in enriched:
    print(f"Evidence ID: {action.evidence_id}")
```

## Troubleshooting

### Проблема: False positives (лишние действия)

**Симптомы**:
```
"General discussion with Ivan" → type="mention", confidence=0.55
```

**Решение**:
1. Повысить confidence threshold (≥0.7 вместо ≥0.5)
2. Добавить негативные паттерны в код (exclude list)
3. Настроить веса в `_calculate_confidence()`

### Проблема: False negatives (пропущенные действия)

**Симптомы**:
```
"Ivan pls review asap" → не извлечено
```

**Решение**:
1. Добавить pattern для "pls" в EN_IMPERATIVE_VERBS
2. Добавить "asap" в deadline patterns
3. Проверить что user alias правильно настроен

### Проблема: Низкий confidence для явных действий

**Симптомы**:
```
"Иван, сделайте до завтра" → confidence=0.6 (expected >0.8)
```

**Решение**:
1. Проверить sender_rank (должен быть >0.5 для важных отправителей)
2. Убедиться что имя user правильно распознано (has_user_mention=True)
3. Настроить bias в логистической функции (сейчас 1.5)

### Проблема: Неправильный тип (action vs question)

**Симптомы**:
```
"Can you review?" → type="action" (expected "question")
```

**Решение**:
1. Проверить порядок проверок в `extract_mentions_actions()`
2. Question markers проверяются ДО imperatives
3. Добавить более точные question patterns

## Настройка и тюнинг

### Добавление новых patterns

**Файл**: `digest-core/src/digest_core/evidence/actions.py`

```python
# Russian imperatives
RU_IMPERATIVE_VERBS = [
    # ... existing ...
    r'\b(завершите?|закончите?|доделай(?:те)?)',  # NEW
]

# English imperatives
EN_IMPERATIVE_VERBS = [
    # ... existing ...
    r'\b(finalize|wrap up|close out)',  # NEW
]
```

### Настройка весов confidence

```python
weights = {
    'has_user_mention': 1.5,      # ↑ увеличить для большей точности
    'has_imperative': 1.2,        # ↑ увеличить для actions
    'has_action_marker': 1.0,
    'is_question': 0.8,           # ↑ увеличить для questions
    'has_deadline': 0.6,
    'sender_rank': 0.5,           # ↑ если важность отправителя критична
}

bias = 1.5  # ↓ уменьшить для более низких порогов
```

### Настройка user aliases

**Файл**: `digest-core/configs/config.yaml`

```yaml
ews:
  user_aliases:
    - ivan.petrov@corp.com
    - ivanov
    - Ivan Petrov
    - Иван Петров
    - IP  # Initials
    - петров.и  # Short name
```

## Testing

### Запуск всех тестов

```bash
cd digest-core
pytest tests/test_actions.py -v
```

### Только Gold Set validation

```bash
pytest tests/test_actions.py::TestGoldSetValidation -v
```

### С coverage

```bash
pytest tests/test_actions.py --cov=digest_core.evidence.actions --cov-report=term
```

**Expected Coverage**: ≥85%

## Roadmap

### v1.0 (текущая реализация)
- ✅ Rule-based RU/EN extraction
- ✅ Confidence scoring (logistic function)
- ✅ Citations integration
- ✅ Prometheus metrics
- ✅ P/R validation (≥0.85/≥0.80)

### v1.1 (планируется)
- 🔄 Sender ranking: автоматическое определение важности отправителей
- 🔄 Fuzzy user matching: nickname resolution ("IP" → "Ivan Petrov")
- 🔄 Date normalization: "завтра" → ISO-8601

### v2.0 (future)
- 🔜 ML-based scoring: дообучение confidence weights на данных
- 🔜 Named Entity Recognition: улучшенное извлечение имен
- 🔜 Multi-language: поддержка DE/FR/ES

## References

- [Email Cleaner Documentation](../src/digest_core/normalize/quotes.py)
- [Citations System](CITATIONS.md)
- [Evidence Split](../src/digest_core/evidence/split.py)
- [Schemas v2](../src/digest_core/llm/schemas.py)

