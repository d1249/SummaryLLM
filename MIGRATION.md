# Migration Guide: V2 → V3

## Overview

This document describes the migration from schema V2 to V3, which removes all PII (Personally Identifiable Information) handling and masking functionality.

**Migration Date**: 2024-12-14
**Schema Version Change**: `2.0` → `3.0`
**Prompt Version**: `v2` → `mvp.5`

---

## What Changed

### 🗑️ Removed Functionality

#### 1. **PII Detection & Masking**
- **Removed**: `digest_core/privacy/` module (all files)
  - `masking.py` - PII detection patterns and masking functions
  - `__init__.py` - Privacy module initialization
- **Removed**: `test_masking.py` - All PII masking tests
- **Impact**: No automatic detection or masking of emails, phone numbers, names, credit cards, passports, SNILS

#### 2. **Configuration**
- **Removed**: `MaskingConfig` class from `config.py`
- **Removed**: `masking.*` section from `config.example.yaml`
- **Removed**: `enforce_input_masking` and `enforce_output_masking` parameters from `LLMGateway`
- **Impact**: Configuration files are simpler, no masking toggles

#### 3. **Metrics**
- **Removed**: `masking_violations_total` Prometheus metric
- **Removed**: `record_masking_violation()` method from `MetricsCollector`
- **Impact**: No tracking of PII leakage violations

#### 4. **Field Changes**
- **Removed**: `owners_masked` field from all schemas (V1, V2)
- **Added**: `owners` field in V3 schemas (plain strings, no masking)
- **Changed**: `actors` (V2) → `owners` (V3) for consistency
- **Impact**: All names are now stored and rendered as plain strings

---

## Schema Changes

### V2 → V3 Field Mapping

| V2 Schema              | V3 Schema              | Notes                           |
|------------------------|------------------------|---------------------------------|
| `actors` (list)        | `owners` (list)        | Renamed, plain strings          |
| `owners_masked` (list) | ❌ Removed             | No longer exists                |
| `participants` (list)  | `participants` (list)  | Unchanged, plain strings        |
| `email_subject`        | ❌ Removed from V3     | Not used in V3 models           |

### V3 Models

```python
# Action Items (V3)
class ActionItemV3(BaseModel):
    title: str
    description: str
    evidence_id: str
    quote: str
    due_date: Optional[str]
    due_date_normalized: Optional[str]
    due_date_label: Optional[str]
    owners: List[str]  # Plain strings (e.g., ["John Smith", "Jane Doe"])
    confidence: str
    response_channel: Optional[str]

# Risk/Blocker Items (V3)
class RiskBlockerV3(BaseModel):
    title: str
    evidence_id: str
    quote: str
    severity: str
    impact: str
    owners: List[str]  # Plain strings

# Deadlines/Meetings (V3)
class DeadlineMeetingV3(BaseModel):
    title: str
    evidence_id: str
    quote: str
    date_time: str
    date_label: Optional[str]
    location: Optional[str]
    participants: List[str]  # Plain strings

# FYI Items (V3)
class FYIItemV3(BaseModel):
    title: str
    evidence_id: str
    quote: str
    category: Optional[str]

# Main Digest (V3)
class EnhancedDigestV3(BaseModel):
    schema_version: str = "3.0"
    prompt_version: str = "mvp.5"
    digest_date: str
    trace_id: str
    timezone: str = "America/Sao_Paulo"
    my_actions: List[ActionItemV3]
    others_actions: List[ActionItemV3]
    deadlines_meetings: List[DeadlineMeetingV3]
    risks_blockers: List[RiskBlockerV3]
    fyi: List[FYIItemV3]
    markdown_summary: Optional[str]
    total_emails_processed: int
    emails_with_actions: int
```

---

## Migration Steps

### For Developers

#### 1. **Update Code**
```bash
# Pull latest changes
git pull origin main

# Update dependencies (if needed)
cd digest-core
source .venv/bin/activate
pip install -e .
```

#### 2. **Update Prompts**
- Use new prompt: `summarize.mvp5.j2`
- Remove all masking instructions from custom prompts
- Update to V3 schema in prompt templates

#### 3. **Update Configuration**
```yaml
# Remove this section from config.yaml
# masking:
#   enforce_input: false
#   enforce_output: false

# Keep only:
degrade:
  enable: true
  mode: "extractive"
```

#### 4. **Update Code References**
```python
# Old (V2)
from digest_core.llm.schemas import EnhancedDigest, ActionItem

digest = EnhancedDigest(
    prompt_version="v2",
    my_actions=[
        ActionItem(
            title="Action",
            actors=["user"],  # Old field
            # ...
        )
    ]
)

# New (V3)
from digest_core.llm.schemas import EnhancedDigestV3, ActionItemV3

digest = EnhancedDigestV3(
    prompt_version="mvp.5",
    my_actions=[
        ActionItemV3(
            title="Action",
            owners=["John Smith"],  # New field, plain strings
            # ...
        )
    ]
)
```

### For Users

#### 1. **No Action Required**
- Existing digests (V2) continue to work
- System automatically uses V2 or V3 based on `prompt_version`

#### 2. **To Use V3**
```bash
# Use V3 by specifying prompt version
python -m digest_core.cli run --prompt-version mvp.5
```

#### 3. **Output Changes**
**Old (V2) Markdown:**
```markdown
**Ответственные:** [[REDACT:NAME]]
```

**New (V3) Markdown:**
```markdown
**Ответственные:** John Smith, Jane Doe
```

---

## Backward Compatibility

### V2 Support
- **V2 schemas remain available** and fully functional
- Use `prompt_version="v2"` to continue using V2
- V2 prompts (`summarize.v2.j2`) still work

### Automatic Detection
```python
# Gateway automatically uses correct schema
if prompt_version in ["mvp.5", "mvp5"]:
    digest = EnhancedDigestV3(**validated)  # Use V3
else:
    digest = EnhancedDigest(**validated)    # Use V2
```

### Rendering
- Markdown renderer supports both V2 (`actors`) and V3 (`owners`)
- Uses `getattr()` to check for both fields
- All names rendered as plain strings (no `[[REDACT:*]]` handling)

---

## Rationale

### Why Remove PII Masking?

1. **Simplification**: PII detection added significant complexity with regex patterns, validation, and special handling
2. **False Positives**: Generic patterns often flagged legitimate content (e.g., phone-like numbers in IDs)
3. **Incomplete Coverage**: Regex-based detection cannot catch all PII variations
4. **LLM Gateway**: If PII handling is needed, it should be done at LLM Gateway level, not in digest pipeline
5. **Transparency**: Plain names in outputs make debugging and verification easier

### What About Security?

- **Access Control**: Security through proper access control, not masking
- **No Logging**: Message bodies never logged (unchanged)
- **Environment Isolation**: Credentials via ENV only (unchanged)
- **TLS**: Corporate CA verification (unchanged)

---

## Testing

### Automated Tests
```bash
# Run V3 tests
cd digest-core
python3 -m pytest tests/test_enhanced_markdown.py::TestEnhancedMarkdownV3 -v

# Expected output:
# test_write_v3_digest_with_plain_owners PASSED
# test_write_v3_digest_with_risk_owners PASSED
# test_v3_backward_compatible_with_v2 PASSED
```

### Manual Testing
```bash
# Test V3 digest generation
python -m digest_core.cli run --dry-run --prompt-version mvp.5

# Verify output contains plain names (no [[REDACT:*]])
cat out/digest-test.md

# Should see:
# **Ответственные:** John Smith, Jane Doe
# NOT: **Ответственные:** [[REDACT:NAME]]
```

---

## Troubleshooting

### Issue: "AttributeError: 'ActionItemV3' object has no attribute 'actors'"
**Solution**: You're using V2 code with V3 schema. Use `owners` instead of `actors`.

### Issue: "Output still shows [[REDACT:*]] patterns"
**Solution**: You're using V2 prompt. Switch to `--prompt-version mvp.5`.

### Issue: "Tests fail after upgrade"
**Solution**: Update test assertions to check for plain names, not masked patterns:
```python
# Old
assert "[[REDACT:NAME]]" in content

# New
assert "John Smith" in content
assert "[[REDACT" not in content
```

---

## Rollback Plan

If you need to rollback to V2:

```bash
# 1. Use V2 prompt
python -m digest_core.cli run --prompt-version v2

# 2. Or checkout previous commit
git checkout <commit-before-v3>

# 3. Reinstall dependencies
cd digest-core
pip install -e .
```

---

## Questions?

For questions or issues with migration:
1. Check existing documentation in `docs/`
2. Review test files for examples
3. Contact development team

---

**Last Updated**: 2024-12-14
**Version**: 3.0

