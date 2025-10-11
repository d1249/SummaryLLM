"""
Test PII policy - all masking handled by LLM Gateway API.
"""
import pytest
from digest_core.normalize.html import HTMLNormalizer


@pytest.fixture
def normalizer():
    return HTMLNormalizer()


def test_no_local_masking(normalizer):
    """No local PII masking - all handled by LLM Gateway API."""
    text = "Contact me at alice@corp.com or call +1-555-123-4567. My name is John Doe."
    masked_text = normalizer.mask_pii(text)
    
    # Text should be returned as-is (no masking)
    assert masked_text == text
    assert "alice@corp.com" in masked_text
    assert "+1-555-123-4567" in masked_text
    assert "John Doe" in masked_text
    assert "[[REDACT:" not in masked_text


def test_mask_pii_compatibility(normalizer):
    """Test that mask_pii method exists for compatibility but does no masking."""
    text = "Test text with various content"
    result = normalizer.mask_pii(text)
    
    # Should return text unchanged
    assert result == text
    assert isinstance(result, str)


def test_html_to_text_still_works(normalizer):
    """Test that HTML to text conversion still works."""
    html_content = "<html><body><p>Hello <b>World</b>!</p></body></html>"
    expected_text = "Hello World!"
    assert normalizer.html_to_text(html_content) == expected_text


def test_truncate_text_still_works(normalizer):
    """Test that text truncation still works."""
    long_text = "a" * 300000  # 300KB
    truncated_text = normalizer.truncate_text(long_text, max_bytes=200000)
    assert len(truncated_text.encode('utf-8')) <= 200000 + len("\n[TRUNCATED]".encode('utf-8'))
    assert "[TRUNCATED]" in truncated_text
