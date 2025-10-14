<!-- f696db6b-77ad-4218-bf20-26d7ea14cf9e b147f3e3-ecf8-42db-bd2e-175e8e5a72d2 -->
# Enhanced Digest Output Schema

## 1. Обновление JSON-схемы дайджеста

**digest-core/src/digest_core/llm/schemas.py**

Расширить схему для включения цитат и нормализованных дат:

```python
class ActionItem(BaseModel):
    """Action item with evidence and quote."""
    title: str = Field(description="Brief action title")
    description: str = Field(description="Detailed description")
    evidence_id: str = Field(description="Evidence ID reference")
    quote: str = Field(description="1-2 sentence quote from evidence")
    due_date: Optional[str] = Field(None, description="ISO-8601 date or 'today'/'tomorrow'")
    due_date_normalized: Optional[str] = Field(None, description="ISO-8601 with TZ America/Sao_Paulo")
    actors: List[str] = Field(default_factory=list, description="People involved")
    confidence: str = Field(description="High/Medium/Low")
    response_channel: Optional[str] = Field(None, description="email/slack/meeting")

class DeadlineMeeting(BaseModel):
    """Deadline or meeting with evidence."""
    title: str
    evidence_id: str
    quote: str
    date_time: str = Field(description="ISO-8601 with TZ")
    date_label: Optional[str] = Field(None, description="'today'/'tomorrow' if applicable")
    location: Optional[str] = None
    participants: List[str] = Field(default_factory=list)

class RiskBlocker(BaseModel):
    """Risk or blocker with evidence."""
    title: str
    evidence_id: str
    quote: str
    severity: str = Field(description="High/Medium/Low")
    impact: str

class FYIItem(BaseModel):
    """FYI item with evidence."""
    title: str
    evidence_id: str
    quote: str
    category: Optional[str] = None

class EnhancedDigest(BaseModel):
    """Enhanced digest with structured sections and evidence references."""
    schema_version: str = Field(default="2.0")
    prompt_version: str
    digest_date: str
    trace_id: str
    timezone: str = Field(default="America/Sao_Paulo")
    
    # Structured sections
    my_actions: List[ActionItem] = Field(default_factory=list)
    others_actions: List[ActionItem] = Field(default_factory=list)
    deadlines_meetings: List[DeadlineMeeting] = Field(default_factory=list)
    risks_blockers: List[RiskBlocker] = Field(default_factory=list)
    fyi: List[FYIItem] = Field(default_factory=list)
    
    # Markdown summary (generated after JSON)
    markdown_summary: Optional[str] = Field(None, description="Brief markdown summary")
```

## 2. Обновление промпта с SYSTEM/RULES/INPUT/OUTPUT

**digest-core/prompts/summarize.v2.j2** (новый файл)

Создать структурированный промпт:

```jinja2
SYSTEM:
Ты — ассистент для создания рабочего дайджеста. Твоя задача — извлечь действия, дедлайны и важную информацию из email-переписки.

Правила:
- Всё должно быть подтверждено цитатами из evidence
- Не домысливай и не интерпретируй сверх написанного
- Каждая запись ОБЯЗАТЕЛЬНО содержит evidence_id и quote (1-2 предложения)
- Даты нормализуй в ISO-8601 формат с TZ America/Sao_Paulo
- Для дат в пределах 48 часов добавляй пометку "today" или "tomorrow"
- Определяй актора (кто должен действовать): user/sender/team

RULES:
1. Цитаты обязательны — без цитаты = не включаем
2. Нормализация дат: "завтра 15:00" → ISO-8601 + label="tomorrow"
3. Actor detection: "Please review" → my_actions; "John will prepare" → others_actions
4. Каналы ответа: email (default), slack, meeting, phone
5. Confidence: High (прямое указание), Medium (подразумевается), Low (неясно)

INPUT:
Дата дайджеста: {{ digest_date }}
Timezone: America/Sao_Paulo
Current datetime: {{ current_datetime }}

Evidence:
{{ evidence }}

OUTPUT FORMAT:
Сначала верни валидный JSON по схеме:
{
  "schema_version": "2.0",
  "digest_date": "{{ digest_date }}",
  "trace_id": "{{ trace_id }}",
  "timezone": "America/Sao_Paulo",
  "my_actions": [
    {
      "title": "...",
      "description": "...",
      "evidence_id": "...",
      "quote": "1-2 sentences from evidence",
      "due_date": "2024-12-15",
      "due_date_normalized": "2024-12-15T15:00:00-03:00",
      "actors": ["user"],
      "confidence": "High",
      "response_channel": "email"
    }
  ],
  "others_actions": [...],
  "deadlines_meetings": [...],
  "risks_blockers": [...],
  "fyi": [...]
}

Затем добавь краткое Markdown-резюме (≤200 слов):
## Краткое резюме
[Главное за период]
```

## 3. Добавление валидации jsonschema

**digest-core/src/digest_core/llm/gateway.py**

Добавить метод валидации с jsonschema:

```python
import jsonschema
from jsonschema import validate, ValidationError

def _validate_enhanced_schema(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate response against enhanced schema using jsonschema."""
    
    # Define JSON schema
    schema = {
        "type": "object",
        "required": ["schema_version", "digest_date", "trace_id", "my_actions"],
        "properties": {
            "schema_version": {"type": "string"},
            "digest_date": {"type": "string"},
            "trace_id": {"type": "string"},
            "timezone": {"type": "string"},
            "my_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["title", "evidence_id", "quote"],
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "evidence_id": {"type": "string"},
                        "quote": {"type": "string", "minLength": 10},
                        "due_date": {"type": ["string", "null"]},
                        "actors": {"type": "array"},
                        "confidence": {"type": "string", "enum": ["High", "Medium", "Low"]}
                    }
                }
            },
            # Similar for others_actions, deadlines_meetings, risks_blockers, fyi
        }
    }
    
    try:
        validate(instance=response_data, schema=schema)
        logger.info("Schema validation passed")
        return response_data
    except ValidationError as e:
        logger.error("Schema validation failed", error=str(e))
        raise ValueError(f"Invalid response schema: {e.message}")
```

Обновить `_validate_response()` для использования новой валидации.

## 4. Утилиты нормализации дат

**digest-core/src/digest_core/llm/date_utils.py** (новый файл)

```python
from datetime import datetime, timedelta
import pytz

def normalize_date_to_tz(date_str: str, base_datetime: datetime, tz_name: str = "America/Sao_Paulo") -> dict:
    """
    Normalize date string to ISO-8601 with timezone.
    
    Returns:
        {
            "normalized": "2024-12-15T15:00:00-03:00",
            "label": "today" | "tomorrow" | None
        }
    """
    tz = pytz.timezone(tz_name)
    base_dt = base_datetime.astimezone(tz)
    
    # Parse date_str (implementation with dateutil.parser)
    # ...
    
    # Check if today/tomorrow
    if parsed_date.date() == base_dt.date():
        label = "today"
    elif parsed_date.date() == (base_dt + timedelta(days=1)).date():
        label = "tomorrow"
    else:
        label = None
    
    return {
        "normalized": parsed_date.isoformat(),
        "label": label
    }
```

## 5. Обновление LLM gateway

**digest-core/src/digest_core/llm/gateway.py**

Обновить `process_digest()`:

```python
def process_digest(self, evidence: List[EvidenceChunk], digest_date: str, 
                  trace_id: str, prompt_version: str = "v2") -> Dict[str, Any]:
    """Process evidence with enhanced prompt and validation."""
    
    # Prepare evidence text (unchanged)
    evidence_text = self._prepare_evidence_text(evidence)
    
    # Calculate current datetime in target timezone
    tz = pytz.timezone("America/Sao_Paulo")
    current_datetime = datetime.now(tz).isoformat()
    
    # Load v2 prompt
    prompt = self._load_prompt(f"summarize.{prompt_version}.j2")
    
    # Render prompt with new variables
    rendered_prompt = prompt.render(
        digest_date=digest_date,
        trace_id=trace_id,
        current_datetime=current_datetime,
        evidence=evidence_text,
        evidence_count=len(evidence)
    )
    
    # Call LLM
    result = self._call_llm(rendered_prompt, trace_id, prompt_version)
    
    # Parse response (JSON + optional Markdown)
    parsed = self._parse_enhanced_response(result['data'])
    
    # Validate with jsonschema
    validated = self._validate_enhanced_schema(parsed)
    
    # Convert to Pydantic model
    digest = EnhancedDigest(**validated)
    
    return {
        "trace_id": trace_id,
        "digest": digest,
        "meta": result['meta']
    }
```

Добавить метод `_parse_enhanced_response()`:

```python
def _parse_enhanced_response(self, response_text: str) -> Dict[str, Any]:
    """Parse response that may contain JSON + Markdown."""
    
    # Try to extract JSON (may be followed by markdown)
    lines = response_text.strip().split('\n')
    
    # Find JSON boundaries
    json_start = 0
    json_end = len(lines)
    
    brace_count = 0
    in_json = False
    json_lines = []
    markdown_lines = []
    
    for i, line in enumerate(lines):
        if not in_json and line.strip().startswith('{'):
            in_json = True
            json_start = i
        
        if in_json:
            json_lines.append(line)
            brace_count += line.count('{') - line.count('}')
            
            if brace_count == 0:
                # JSON ended
                json_end = i + 1
                markdown_lines = lines[json_end:]
                break
    
    # Parse JSON
    json_str = '\n'.join(json_lines)
    parsed = json.loads(json_str)
    
    # Add markdown if present
    if markdown_lines:
        markdown_text = '\n'.join(markdown_lines).strip()
        if markdown_text:
            parsed['markdown_summary'] = markdown_text
    
    return parsed
```

## 6. Тесты

**digest-core/tests/test_enhanced_digest.py** (новый файл)

```python
class TestEnhancedDigest:
    def test_schema_validation_with_evidence_id_and_quote(self):
        """Test that all items have evidence_id and quote."""
        
    def test_date_normalization_today_tomorrow(self):
        """Test dates normalized to ISO-8601 with today/tomorrow labels."""
        
    def test_response_channel_detection(self):
        """Test detection of response channel (email/slack/meeting)."""
        
    def test_actor_detection_my_vs_others(self):
        """Test correct classification into my_actions vs others_actions."""
        
    def test_json_and_markdown_consistency(self):
        """Test that markdown summary doesn't contradict JSON."""
        
    def test_schema_validation_rejects_missing_evidence_id(self):
        """Test that validation fails if evidence_id is missing."""
        
    def test_schema_validation_rejects_short_quote(self):
        """Test that validation fails if quote is too short."""
```

## 7. Обновление ассемблеров

**digest-core/src/digest_core/assemble/markdown.py**

Обновить для работы с EnhancedDigest:

```python
def assemble_markdown(digest: EnhancedDigest, output_path: Path) -> None:
    """Assemble markdown from enhanced digest."""
    
    lines = []
    lines.append(f"# Дайджест действий - {digest.digest_date}")
    lines.append(f"*Trace ID: {digest.trace_id}*")
    lines.append(f"*Timezone: {digest.timezone}*")
    lines.append("")
    
    # My actions
    if digest.my_actions:
        lines.append("## Мои действия")
        for i, action in enumerate(digest.my_actions, 1):
            lines.append(f"### {i}. {action.title}")
            lines.append(f"**Описание:** {action.description}")
            lines.append(f"**Срок:** {action.due_date or 'Не указан'}")
            if action.due_date_normalized:
                label = f" ({action.due_date_label})" if action.due_date_label else ""
                lines.append(f"**Дата (ISO):** {action.due_date_normalized}{label}")
            lines.append(f"**Уверенность:** {action.confidence}")
            lines.append(f"**Источник:** Evidence {action.evidence_id}")
            lines.append(f"**Цитата:** \"{action.quote}\"")
            lines.append("")
    
    # Similar for others_actions, deadlines_meetings, etc.
    
    # Add markdown summary if present
    if digest.markdown_summary:
        lines.append("---")
        lines.append(digest.markdown_summary)
    
    # Write
    output_path.write_text('\n'.join(lines), encoding='utf-8')
```

## 8. Интеграция в run.py

**digest-core/src/digest_core/run.py**

Обновить для использования v2 промпта:

```python
# Step 6: Process with LLM
prompt_version = "v2"  # Use enhanced prompt
result = llm_gateway.process_digest(
    selected_evidence, 
    digest_date, 
    trace_id,
    prompt_version=prompt_version
)

digest = result['digest']  # EnhancedDigest instance
```

## Acceptance Criteria

1. ✅ Все записи содержат `evidence_id` и `quote` (≥10 символов)
2. ✅ Даты нормализованы в ISO-8601 с TZ America/Sao_Paulo
3. ✅ Даты в пределах 48 часов помечены "today"/"tomorrow"
4. ✅ JSON проходит jsonschema валидацию
5. ✅ Markdown-резюме не противоречит JSON (проверяется тестом)
6. ✅ Actor detection работает корректно (my_actions vs others_actions)
7. ✅ Response channel определяется из контекста
8. ✅ Все новые тесты зелёные

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