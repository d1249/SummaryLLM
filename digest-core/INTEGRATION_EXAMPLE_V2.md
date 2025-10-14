# Enhanced Digest v2 - Пример интеграции в run.py

## Быстрый старт

Этот файл показывает как интегрировать Enhanced Digest v2 в существующий pipeline.

## 1. Обновление run.py для v2

### Вариант A: Добавить флаг версии

```python
# digest-core/src/digest_core/run.py

def run_digest(config: Config, trace_id: str = None, digest_version: str = "v1") -> str:
    """
    Run digest generation pipeline.
    
    Args:
        config: Configuration object
        trace_id: Optional trace ID
        digest_version: "v1" (legacy) or "v2" (enhanced)
    
    Returns:
        Path to generated digest
    """
    if trace_id is None:
        trace_id = str(uuid.uuid4())[:8]
    
    # ... existing code ...
    
    # Step 6: Process with LLM
    if digest_version == "v2":
        result = llm_gateway.process_digest(
            selected_evidence, 
            digest_date, 
            trace_id,
            prompt_version="v2"
        )
        
        digest = result['digest']  # EnhancedDigest instance
        
        # Step 7: Assemble output
        from digest_core.assemble.markdown import MarkdownAssembler
        from digest_core.assemble.jsonout import JSONAssembler
        
        assembler = MarkdownAssembler()
        assembler.write_enhanced_digest(digest, output_path / f"digest-{digest_date}.md")
        
        # Optional: JSON output
        json_assembler = JSONAssembler()
        json_output = json_assembler.assemble_enhanced(digest)
        (output_path / f"digest-{digest_date}.json").write_text(
            json.dumps(json_output, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
    else:
        # Legacy v1 flow
        result = llm_gateway.extract_actions(selected_evidence, prompt_template, trace_id)
        # ... existing v1 code ...
    
    return str(output_path)
```

### Вариант B: Новая функция run_digest_v2()

```python
# digest-core/src/digest_core/run.py

def run_digest_v2(config: Config, trace_id: str = None) -> Dict[str, Any]:
    """
    Run enhanced digest generation pipeline (v2).
    
    Args:
        config: Configuration object
        trace_id: Optional trace ID
    
    Returns:
        Dict with digest_path, trace_id, and meta
    """
    if trace_id is None:
        trace_id = str(uuid.uuid4())[:8]
    
    logger.info("Starting enhanced digest v2 generation", trace_id=trace_id)
    
    # Step 1-5: Same as v1 (ingest, normalize, threads, split, select)
    # ... (reuse existing code) ...
    
    # Step 6: Process with enhanced v2 LLM gateway
    llm_gateway = LLMGateway(config.llm)
    
    result = llm_gateway.process_digest(
        evidence=selected_evidence,
        digest_date=digest_date,
        trace_id=trace_id,
        prompt_version="v2"
    )
    
    digest = result['digest']  # EnhancedDigest instance
    meta = result['meta']
    
    # Step 7: Assemble outputs
    output_path = Path("output")
    output_path.mkdir(exist_ok=True)
    
    # Markdown
    from digest_core.assemble.markdown import MarkdownAssembler
    md_assembler = MarkdownAssembler()
    md_path = output_path / f"digest-{digest_date}.md"
    md_assembler.write_enhanced_digest(digest, md_path)
    
    # JSON
    json_path = output_path / f"digest-{digest_date}.json"
    json_path.write_text(
        digest.model_dump_json(indent=2, exclude_none=True),
        encoding='utf-8'
    )
    
    logger.info("Enhanced digest v2 completed",
               trace_id=trace_id,
               md_path=str(md_path),
               json_path=str(json_path),
               my_actions=len(digest.my_actions),
               others_actions=len(digest.others_actions))
    
    return {
        "digest_path": str(md_path),
        "json_path": str(json_path),
        "trace_id": trace_id,
        "digest": digest,
        "meta": meta
    }
```

## 2. Обновление CLI (cli.py)

```python
# digest-core/src/digest_core/cli.py

@app.command()
def generate(
    config_path: str = typer.Option("configs/config.yaml", help="Path to config file"),
    version: str = typer.Option("v2", help="Digest version: v1 or v2"),
    output_format: str = typer.Option("both", help="Output format: markdown, json, or both"),
    trace_id: str = typer.Option(None, help="Custom trace ID")
):
    """Generate digest from emails."""
    try:
        config = load_config(config_path)
        
        if version == "v2":
            result = run_digest_v2(config, trace_id)
            typer.echo(f"✅ Enhanced digest v2 generated:")
            typer.echo(f"   Markdown: {result['digest_path']}")
            typer.echo(f"   JSON: {result['json_path']}")
            typer.echo(f"   Trace ID: {result['trace_id']}")
        else:
            # Legacy v1
            result = run_digest(config, trace_id, digest_version="v1")
            typer.echo(f"✅ Digest v1 generated: {result}")
        
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)
```

## 3. JSON Assembler для v2 (если нужен отдельный)

```python
# digest-core/src/digest_core/assemble/jsonout.py

from digest_core.llm.schemas import EnhancedDigest

class JSONAssembler:
    """Assemble digest data into JSON output."""
    
    def assemble_enhanced(self, digest: EnhancedDigest) -> Dict[str, Any]:
        """
        Assemble EnhancedDigest into JSON-serializable dict.
        
        Args:
            digest: EnhancedDigest instance
        
        Returns:
            Dict ready for JSON serialization
        """
        return digest.model_dump(exclude_none=True, mode='json')
```

## 4. Конфигурация (опционально)

Добавить в `config.yaml`:

```yaml
# Enhanced digest v2 settings
digest:
  version: "v2"  # "v1" or "v2"
  timezone: "America/Sao_Paulo"
  output_formats:
    - markdown
    - json
```

И в `config.py`:

```python
class DigestConfig(BaseModel):
    """Digest generation configuration."""
    version: str = Field(default="v2", description="Digest version: v1 or v2")
    timezone: str = Field(default="America/Sao_Paulo", description="Timezone for dates")
    output_formats: List[str] = Field(default=["markdown", "json"])

class Config(BaseSettings):
    # ... existing fields ...
    digest: DigestConfig = Field(default_factory=DigestConfig)
```

## 5. Использование в коде

### Простой пример

```python
from digest_core.config import Config
from digest_core.run import run_digest_v2

# Load config
config = Config()

# Run v2 pipeline
result = run_digest_v2(config)

# Access results
digest = result['digest']
print(f"My actions: {len(digest.my_actions)}")
print(f"Deadlines: {len(digest.deadlines_meetings)}")

# Get specific action
if digest.my_actions:
    first_action = digest.my_actions[0]
    print(f"Action: {first_action.title}")
    print(f"Quote: {first_action.quote}")
    print(f"Evidence: {first_action.evidence_id}")
```

### Миграция существующего кода

**Было (v1):**
```python
result = llm_gateway.extract_actions(evidence, prompt_template, trace_id)
sections = result.get("sections", [])
```

**Стало (v2):**
```python
result = llm_gateway.process_digest(evidence, digest_date, trace_id, "v2")
digest = result["digest"]  # EnhancedDigest
my_actions = digest.my_actions
```

## 6. Тестирование интеграции

```python
# tests/test_integration_v2.py

def test_full_pipeline_v2(test_config):
    """Test full v2 pipeline end-to-end."""
    result = run_digest_v2(test_config, trace_id="test_123")
    
    assert result["trace_id"] == "test_123"
    assert Path(result["digest_path"]).exists()
    assert Path(result["json_path"]).exists()
    
    digest = result["digest"]
    assert isinstance(digest, EnhancedDigest)
    assert digest.schema_version == "2.0"
```

## 7. Обратная совместимость

Для поддержки обоих версий одновременно:

```python
def run_digest_universal(config: Config, version: str = "v2", **kwargs):
    """Universal digest runner supporting both v1 and v2."""
    if version == "v2":
        return run_digest_v2(config, **kwargs)
    elif version == "v1":
        return run_digest(config, digest_version="v1", **kwargs)
    else:
        raise ValueError(f"Unknown digest version: {version}")
```

## 8. Пример скрипта для миграции

```bash
#!/bin/bash
# migrate_to_v2.sh

# Generate v2 digest for last 24 hours
python -m digest_core.cli generate \
    --version v2 \
    --config-path configs/config.yaml \
    --output-format both

# Compare with v1 (for validation)
python -m digest_core.cli generate \
    --version v1 \
    --config-path configs/config.yaml \
    --output-format markdown
```

## Заключение

Enhanced Digest v2 полностью готов к интеграции. Ключевые преимущества:

- ✅ Структурированные данные с валидацией
- ✅ Обязательные цитаты и evidence_id
- ✅ Нормализация дат
- ✅ Обратная совместимость с v1
- ✅ Простая миграция

Выберите один из вариантов интеграции (A или B) в зависимости от ваших требований.

