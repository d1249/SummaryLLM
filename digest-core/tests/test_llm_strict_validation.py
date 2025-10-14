"""
Tests for strict LLM JSON validation.
"""
import pytest
import json
from digest_core.llm.models import parse_llm_json, LLMResponse, minimal_json_repair


def test_valid_json_parses():
    """Test that valid JSON parses correctly."""
    raw = '{"version":"v1","evidence":[{"thread_id":"t1","message_ids":["m1"],"quote":"test"}],"summary":[{"title":"A","detail":"B"}]}'
    obj = parse_llm_json(raw, strict=True)
    assert isinstance(obj, LLMResponse)
    assert obj.version == "v1"
    assert len(obj.evidence) == 1
    assert len(obj.summary) == 1
    assert obj.summary[0].title == "A"


def test_invalid_json_raises_strict():
    """Test that invalid JSON raises in strict mode."""
    raw = '{"version":"v1","evidence":[{"thread_id":"t1"}]}'  # broken JSON
    with pytest.raises(ValueError, match="Invalid LLM JSON"):
        parse_llm_json(raw, strict=True)


def test_minimal_json_cleanup():
    """Test minimal JSON cleanup."""
    # Markdown code block
    text = '```json\n{"key": "value"}\n```'
    cleaned = minimal_json_repair(text)
    assert "```" not in cleaned
    assert '{"key": "value"}' in cleaned
    
    # Trim to last brace
    text = '{"key": "value"}some garbage'
    cleaned = minimal_json_repair(text)
    assert cleaned == '{"key": "value"}'


def test_non_strict_mode_attempts_repair():
    """Test that non-strict mode attempts repair."""
    raw = '```json\n{"version":"v1","evidence":[],"summary":[]}\n```'
    obj = parse_llm_json(raw, strict=False)
    assert isinstance(obj, LLMResponse)

