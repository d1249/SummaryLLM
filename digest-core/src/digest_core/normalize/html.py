"""
HTML to text normalization.
This module provides basic HTML to text conversion.
"""
import re
import html
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger()


class HTMLNormalizer:
    """HTML to text conversion."""
    
    def __init__(self):
        pass
    
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
