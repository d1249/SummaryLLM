"""
HTML to text normalization and PII masking.
"""
import re
import html
from typing import List, Dict
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger()


class HTMLNormalizer:
    """HTML to text conversion and PII masking."""
    
    def __init__(self):
        # PII patterns for masking
        self.pii_patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'(\+?[1-9]\d{1,14})|(\(\d{3}\)\s?\d{3}-\d{4})|(\d{3}-\d{3}-\d{4})'),
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            'credit_card': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
            'ip_address': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
        }
        
        # Common name patterns (simplified)
        self.name_patterns = [
            re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'),  # First Last
            re.compile(r'\b[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+\b'),  # First M. Last
        ]
    
    def html_to_text(self, html_content: str) -> str:
        """Convert HTML to clean text."""
        if not html_content:
            return ""
        
        try:
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Remove tracking pixels and images
            for img in soup.find_all('img'):
                src = img.get('src', '')
                # Remove inline attachments (cid:)
                if src.startswith('cid:'):
                    img.decompose()
                # Remove 1x1 tracking pixels
                elif (img.get('width') == '1' or img.get('height') == '1'):
                    img.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Decode HTML entities
            text = html.unescape(text)
            
            return text
            
        except Exception as e:
            logger.warning("HTML parsing failed, using raw text", error=str(e))
            # Fallback: basic HTML tag removal
            text = re.sub(r'<[^>]+>', '', html_content)
            text = html.unescape(text)
            return text
    
    def mask_pii(self, text: str) -> str:
        """Mask PII in text with [[REDACT:TYPE]] markers."""
        if not text:
            return text
        
        masked_text = text
        
        # Mask emails
        masked_text = self.pii_patterns['email'].sub('[[REDACT:EMAIL]]', masked_text)
        
        # Mask phone numbers
        masked_text = self.pii_patterns['phone'].sub('[[REDACT:PHONE]]', masked_text)
        
        # Mask SSNs
        masked_text = self.pii_patterns['ssn'].sub('[[REDACT:SSN]]', masked_text)
        
        # Mask credit cards
        masked_text = self.pii_patterns['credit_card'].sub('[[REDACT:CARD]]', masked_text)
        
        # Mask IP addresses
        masked_text = self.pii_patterns['ip_address'].sub('[[REDACT:IP]]', masked_text)
        
        # Mask names (simplified approach)
        for pattern in self.name_patterns:
            masked_text = pattern.sub('[[REDACT:NAME]]', masked_text)
        
        # Denylist check: verify no raw PII patterns remain
        self._validate_no_leakage(masked_text)
        
        return masked_text
    
    def _validate_no_leakage(self, text: str) -> None:
        """Validate that no raw PII patterns remain after masking."""
        # Check for email leakage
        if self.pii_patterns['email'].search(text):
            leaked = self.pii_patterns['email'].findall(text)
            logger.warning("Email leakage detected after masking", leaked_count=len(leaked))
        
        # Check for phone leakage
        if self.pii_patterns['phone'].search(text):
            logger.warning("Phone leakage detected after masking")
        
        # Check for SSN leakage
        if self.pii_patterns['ssn'].search(text):
            logger.warning("SSN leakage detected after masking")
        
        # Check for credit card leakage
        if self.pii_patterns['credit_card'].search(text):
            logger.warning("Credit card leakage detected after masking")
    
    def truncate_text(self, text: str, max_bytes: int = 200000) -> str:
        """Truncate text if it exceeds size limit."""
        if len(text.encode('utf-8')) <= max_bytes:
            return text
        
        # Truncate to fit within byte limit
        truncated = text.encode('utf-8')[:max_bytes].decode('utf-8', errors='ignore')
        
        # Add truncation marker
        truncated += "\n[TRUNCATED]"
        
        logger.warning("Text truncated", original_size=len(text), truncated_size=len(truncated))
        
        return truncated
