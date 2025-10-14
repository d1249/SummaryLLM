"""
PII (Personally Identifiable Information) masking utilities.

Masks sensitive information before sending to LLM and validates output.
"""
import re
from typing import Dict, Any
import structlog

logger = structlog.get_logger()

# Regex patterns for PII detection
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    re.IGNORECASE
)

PHONE_PATTERN = re.compile(
    r'(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b'
)

# Card numbers (13-19 digits with optional spaces/dashes)
CARD_PATTERN = re.compile(
    r'\b(?:\d[\s-]*?){13,19}\b'
)

# Russian passport (серия номер: 4 цифры пробел 6 цифр)
PASSPORT_RU_PATTERN = re.compile(
    r'\b\d{4}\s?\d{6}\b'
)

# СНИЛС (xxx-xxx-xxx xx)
SNILS_PATTERN = re.compile(
    r'\b\d{3}-\d{3}-\d{3}\s\d{2}\b'
)


def mask_text(text: str, *, enforce: bool = True) -> str:
    """
    Mask PII in text.
    
    Replaces:
    - Email addresses → [[REDACT:EMAIL]]
    - Phone numbers → [[REDACT:PHONE]]
    - Card numbers → [[REDACT:CARD]]
    - Russian passports → [[REDACT:PASSPORT]]
    - СНИЛС → [[REDACT:SNILS]]
    
    Args:
        text: Input text
        enforce: If False, just count PII (for testing)
    
    Returns:
        Masked text
    """
    if not text:
        return text
    
    masked = text
    pii_count = 0
    
    # Mask emails
    email_matches = EMAIL_PATTERN.findall(text)
    if email_matches:
        pii_count += len(email_matches)
        masked = EMAIL_PATTERN.sub("[[REDACT:EMAIL]]", masked)
    
    # Mask phones
    phone_matches = PHONE_PATTERN.findall(text)
    if phone_matches:
        pii_count += len(phone_matches)
        masked = PHONE_PATTERN.sub("[[REDACT:PHONE]]", masked)
    
    # Mask card numbers (but be careful with false positives)
    card_matches = CARD_PATTERN.findall(text)
    if card_matches:
        # Filter out false positives (dates, etc.)
        real_cards = [c for c in card_matches if len(c.replace('-', '').replace(' ', '')) >= 13]
        if real_cards:
            pii_count += len(real_cards)
            masked = CARD_PATTERN.sub("[[REDACT:CARD]]", masked)
    
    # Mask Russian passports
    passport_matches = PASSPORT_RU_PATTERN.findall(text)
    if passport_matches:
        pii_count += len(passport_matches)
        masked = PASSPORT_RU_PATTERN.sub("[[REDACT:PASSPORT]]", masked)
    
    # Mask SNILS
    snils_matches = SNILS_PATTERN.findall(text)
    if snils_matches:
        pii_count += len(snils_matches)
        masked = SNILS_PATTERN.sub("[[REDACT:SNILS]]", masked)
    
    if pii_count > 0:
        logger.info("PII masked in text", pii_count=pii_count)
    
    return masked


def assert_no_unmasked_pii(text: str) -> None:
    """
    Assert that text contains no unmasked PII.
    
    Args:
        text: Text to check
    
    Raises:
        ValueError: If PII detected
    """
    if not text:
        return
    
    violations = []
    
    if EMAIL_PATTERN.search(text):
        violations.append("EMAIL")
    
    if PHONE_PATTERN.search(text):
        violations.append("PHONE")
    
    if CARD_PATTERN.search(text):
        violations.append("CARD")
    
    if PASSPORT_RU_PATTERN.search(text):
        violations.append("PASSPORT")
    
    if SNILS_PATTERN.search(text):
        violations.append("SNILS")
    
    if violations:
        preview = text[:200] if len(text) > 200 else text
        raise ValueError(
            f"PII leakage detected: {', '.join(violations)}. "
            f"Preview: {preview}"
        )


def mask_dict_values(data: Dict[str, Any], *, enforce: bool = True) -> Dict[str, Any]:
    """
    Recursively mask PII in dictionary values.
    
    Args:
        data: Dictionary to mask
        enforce: If True, apply masking
    
    Returns:
        Dictionary with masked values
    """
    if not isinstance(data, dict):
        return data
    
    masked = {}
    for key, value in data.items():
        if isinstance(value, str):
            masked[key] = mask_text(value, enforce=enforce)
        elif isinstance(value, dict):
            masked[key] = mask_dict_values(value, enforce=enforce)
        elif isinstance(value, list):
            masked[key] = [
                mask_dict_values(item, enforce=enforce) if isinstance(item, dict)
                else mask_text(item, enforce=enforce) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            masked[key] = value
    
    return masked


def validate_llm_output(output: str, *, enforce: bool = True) -> None:
    """
    Validate that LLM output contains no PII.
    
    Args:
        output: LLM output text
        enforce: If True, raise on PII detection
    
    Raises:
        ValueError: If PII detected and enforce=True
    """
    if not enforce:
        return
    
    try:
        assert_no_unmasked_pii(output)
    except ValueError as e:
        logger.error("PII leakage in LLM output detected", error=str(e))
        raise

