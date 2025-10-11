"""
Quote and signature cleaning for email normalization.
"""
import re
import structlog

logger = structlog.get_logger()


class QuoteCleaner:
    """Clean quotes, signatures, and disclaimers from email content."""
    
    def __init__(self):
        # Quote markers in different languages and formats
        self.quote_markers = [
            r'-----Original Message-----',
            r'----- Переадресованное сообщение -----',
            r'From:',
            r'От:',
            r'Переадресовано:',
            r'Forwarded:',
            r'Re:',
            r'Re:',
            r'^> ',  # Quote prefix
            r'^>',   # Quote prefix without space
        ]
        
        # Signature patterns
        self.signature_patterns = [
            r'Best regards,?\s*$',
            r'С уважением,?\s*$',
            r'Sent from my iPhone',
            r'Sent from my Android',
            r'Отправлено с iPhone',
            r'Отправлено с Android',
            r'Get Outlook for (iOS|Android)',
            r'Microsoft Outlook',
        ]
        
        # Disclaimer patterns
        self.disclaimer_patterns = [
            r'DISCLAIMER.*?$',
            r'LEGAL NOTICE.*?$',
            r'CONFIDENTIALITY.*?$',
            r'This email originated from.*?$',
            r'This message is confidential.*?$',
        ]
        
        # Compile patterns
        self.quote_regex = re.compile('|'.join(self.quote_markers), re.MULTILINE | re.IGNORECASE)
        self.signature_regex = re.compile('|'.join(self.signature_patterns), re.MULTILINE | re.IGNORECASE)
        self.disclaimer_regex = re.compile('|'.join(self.disclaimer_patterns), re.MULTILINE | re.IGNORECASE | re.DOTALL)
    
    def clean_quotes(self, text: str) -> str:
        """Remove quotes, signatures, and disclaimers from email text."""
        if not text:
            return text
        
        cleaned_text = text
        
        # Remove disclaimers first (they're usually at the end)
        cleaned_text = self.disclaimer_regex.sub('', cleaned_text)
        
        # Remove signatures
        cleaned_text = self.signature_regex.sub('', cleaned_text)
        
        # Remove quotes (up to 5 levels deep)
        cleaned_text = self._remove_quotes_recursive(cleaned_text, max_levels=5)
        
        # Clean up extra whitespace
        cleaned_text = self._clean_whitespace(cleaned_text)
        
        return cleaned_text
    
    def _remove_quotes_recursive(self, text: str, max_levels: int = 5) -> str:
        """Remove quoted text recursively."""
        lines = text.split('\n')
        cleaned_lines = []
        in_quote = False
        quote_level = 0
        
        for line in lines:
            # Check if line starts a quote
            if self.quote_regex.search(line):
                in_quote = True
                quote_level = 1
                continue  # Skip the quote marker line
            
            # Check quote level by counting '>' prefixes
            if in_quote:
                quote_prefix_count = len(line) - len(line.lstrip('>'))
                if quote_prefix_count > 0:
                    quote_level = quote_prefix_count
                    if quote_level <= max_levels:
                        continue  # Skip this quoted line
                    else:
                        # Quote level too deep, stop quoting
                        in_quote = False
                        quote_level = 0
                else:
                    # No quote prefix, end of quote
                    in_quote = False
                    quote_level = 0
                    continue  # Skip the first non-quoted line after quote
            
            # Add non-quoted lines
            if not in_quote:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _clean_whitespace(self, text: str) -> str:
        """Clean up excessive whitespace."""
        # Replace multiple newlines with single newline
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Remove leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split('\n')]
        
        # Remove empty lines at start and end
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        
        return '\n'.join(lines)
    
    def extract_main_content(self, text: str) -> str:
        """Extract the main content, removing all quotes and signatures."""
        # First pass: remove quotes
        main_content = self.clean_quotes(text)
        
        # Second pass: try to identify the actual message content
        # Look for patterns that indicate the start of the main message
        lines = main_content.split('\n')
        content_start = 0
        
        # Skip common email headers/patterns
        skip_patterns = [
            r'^Subject:',
            r'^To:',
            r'^From:',
            r'^Date:',
            r'^Sent:',
            r'^Received:',
        ]
        
        for i, line in enumerate(lines):
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                content_start = i + 1
            elif line.strip() and not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}', line):
                # Found non-header content
                content_start = i
                break
        
        # Extract content from identified start
        main_lines = lines[content_start:]
        
        # Remove trailing empty lines
        while main_lines and not main_lines[-1].strip():
            main_lines.pop()
        
        return '\n'.join(main_lines)
