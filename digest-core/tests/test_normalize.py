"""
Tests for normalization functionality.
"""
import pytest
from digest_core.normalize.html import HTMLNormalizer
from digest_core.normalize.quotes import QuoteCleaner


def test_html_to_text():
    """Test HTML to text conversion."""
    normalizer = HTMLNormalizer()
    
    html = "<html><body><p>Hello <b>world</b>!</p></body></html>"
    text = normalizer.html_to_text(html)
    
    assert "Hello world!" in text
    assert "<html>" not in text
    assert "<b>" not in text


def test_style_removal():
    """Test that style tags are removed."""
    normalizer = HTMLNormalizer()
    
    html = "<html><style>body { color: red; }</style><body>Content</body></html>"
    text = normalizer.html_to_text(html)
    
    assert "color: red" not in text
    assert "Content" in text


def test_tracking_pixel_removal():
    """Test that tracking pixels are removed."""
    normalizer = HTMLNormalizer()
    
    html = '<img src="cid:tracker" width="1" height="1">Content'
    text = normalizer.html_to_text(html)
    
    assert "Content" in text


def test_truncate_large_text():
    """Test that large texts are truncated."""
    normalizer = HTMLNormalizer()
    
    # Create text larger than 200KB
    large_text = "x" * 300000
    truncated = normalizer.truncate_text(large_text, max_bytes=200000)
    
    assert len(truncated.encode('utf-8')) <= 200000 + 100  # Allow for marker
    assert "[TRUNCATED]" in truncated


def test_quote_cleaning():
    """Test quote cleaning."""
    cleaner = QuoteCleaner()
    
    text = """
    This is my message.
    
    -----Original Message-----
    From: someone@example.com
    This is quoted text.
    """
    
    cleaned = cleaner.clean_quotes(text)
    
    assert "This is my message" in cleaned
    assert "Original Message" not in cleaned
    assert "quoted text" not in cleaned


def test_signature_removal():
    """Test signature removal."""
    cleaner = QuoteCleaner()
    
    text = """
    Message content here.
    
    Best regards,
    John Doe
    """
    
    cleaned = cleaner.clean_quotes(text)
    
    assert "Message content" in cleaned
    # Signature should be removed or minimized


def test_multilevel_quotes():
    """Test removal of multi-level quotes."""
    cleaner = QuoteCleaner()
    
    text = """
    My response
    > First level quote
    >> Second level quote
    >>> Third level quote
    """
    
    cleaned = cleaner.clean_quotes(text)
    
    assert "My response" in cleaned
    # Quotes should be removed


def test_mask_pii_no_masking():
    """Test that mask_pii does no masking (handled by LLM Gateway API)."""
    normalizer = HTMLNormalizer()
    
    text = "Contact John Doe at john@company.com or call +1-555-123-4567."
    masked_text = normalizer.mask_pii(text)
    
    # Text should be returned unchanged
    assert masked_text == text
    assert "John Doe" in masked_text
    assert "john@company.com" in masked_text
    assert "+1-555-123-4567" in masked_text
    assert "[[REDACT:" not in masked_text

