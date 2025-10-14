"""
Quote and signature cleaning for email normalization.
"""
import re
import structlog

logger = structlog.get_logger()


class QuoteCleaner:
    """Clean quotes, signatures, and disclaimers from email content."""
    
    def __init__(self, keep_top_quote_head: bool = True):
        """
        Initialize QuoteCleaner.
        
        Args:
            keep_top_quote_head: If True, keep 1-2 paragraphs from the top-level quote
                                 to preserve inline replies and context.
        """
        self.keep_top_quote_head = keep_top_quote_head
        
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
        
        # Quote header patterns (On ... wrote:, От: <email> Дата:)
        self.quote_header_patterns = [
            r'^On .+ wrote:',
            r'^On .+ at .+ wrote:',
            r'^.+ <.+@.+> wrote:',
            r'^От: .+',
            r'^Дата: .+',
            r'^From: .+',
            r'^Date: .+',
            r'^Sent: .+',
            r'^Отправлено: .+',
        ]
        self.quote_header_regex = re.compile('|'.join(self.quote_header_patterns), re.MULTILINE | re.IGNORECASE)
        
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
        """Remove quoted text recursively, optionally keeping top-level quote head."""
        if not self.keep_top_quote_head:
            # Legacy behavior: remove all quotes
            return self._remove_all_quotes(text, max_levels)
        
        lines = text.split('\n')
        cleaned_lines = []
        quote_state = None  # None, 'collecting_top', 'deep_quote', 'awaiting_quote_body'
        top_quote_lines = []
        seen_quote_header = False
        max_top_quote_lines = 10
        max_top_quote_paragraphs = 2
        consecutive_empty = 0
        paragraphs_collected = 0
        in_paragraph = False
        
        i = 0
        while i < len(lines):
            line = lines[i]
            quote_prefix_count = len(line) - len(line.lstrip('>'))
            
            # Check if this is a quote marker line (-----Original Message-----, From:, etc.)
            is_quote_marker = False
            if quote_prefix_count == 0:  # Not a > quoted line
                # Check for explicit markers
                for pattern in [r'-----Original Message-----', r'----- Переадресованное сообщение -----']:
                    if re.search(pattern, line, re.IGNORECASE):
                        is_quote_marker = True
                        break
                
                # Check for quote headers (On ... wrote:, От:, From:) only if not in a quote yet
                if not is_quote_marker and quote_state is None:
                    if self.quote_header_regex.search(line):
                        seen_quote_header = True
                        # Check if next lines have > prefix (MS Outlook style) or not (inline style)
                        # Peek ahead to see if there are > lines coming
                        has_prefixed_lines_ahead = False
                        for j in range(i + 1, min(i + 5, len(lines))):
                            future_line = lines[j]
                            if future_line.strip() and future_line.lstrip().startswith('>'):
                                has_prefixed_lines_ahead = True
                                break
                        
                        if has_prefixed_lines_ahead:
                            # Outlook-style: От:, Дата: without >, then > quoted content
                            quote_state = 'awaiting_quote_body'
                            top_quote_lines = []
                            consecutive_empty = 0
                            paragraphs_collected = 0
                            in_paragraph = False
                        else:
                            # Inline style: On ... wrote: directly followed by > quoted content
                            quote_state = 'collecting_top'
                            top_quote_lines = []
                            consecutive_empty = 0
                            paragraphs_collected = 0
                            in_paragraph = False
                        i += 1
                        continue
            
            # State machine
            if quote_state == 'awaiting_quote_body':
                # In MS Outlook style, we've seen От:/Дата: and waiting for > content
                # Skip any metadata lines (От:, Дата:, etc.)
                if quote_prefix_count == 0:
                    if any(re.match(p, line.strip(), re.IGNORECASE) for p in [r'^От:', r'^Дата:', r'^From:', r'^Date:', r'^Sent:', r'^To:', r'^Subject:', r'^Кому:', r'^Тема:']):
                        # Still in metadata, skip
                        i += 1
                        continue
                    elif not line.strip():
                        # Empty line between metadata and body
                        i += 1
                        continue
                    else:
                        # Non-metadata, non-> line - probably end of quote or malformed
                        quote_state = None
                        cleaned_lines.append(line)
                        i += 1
                        continue
                else:
                    # Found > line, start collecting
                    quote_state = 'collecting_top'
                    # Don't increment i, let collecting_top process this line
                    continue
            
            elif quote_state == 'collecting_top':
                # Check if we've already collected enough before processing this line
                if len(top_quote_lines) >= max_top_quote_lines:
                    # Already collected max lines, save and switch to deep_quote
                    if top_quote_lines:
                        cleaned_lines.append('[Quoted head retained]')
                        for qline in top_quote_lines:
                            cleaned_lines.append(f'> {qline}')
                        cleaned_lines.append('')
                    quote_state = 'deep_quote'
                    # Continue to process this line in deep_quote state
                    continue
                
                if quote_prefix_count == 1:
                    # Single-level quote line
                    stripped_line = line.lstrip('>').strip()
                    
                    # Check if this line itself starts a deeper quote
                    if stripped_line.startswith('>'):
                        # Found nested quote (> >), save what we have and go to deep_quote
                        if top_quote_lines:
                            cleaned_lines.append('[Quoted head retained]')
                            for qline in top_quote_lines:
                                cleaned_lines.append(f'> {qline}')
                            cleaned_lines.append('')
                        quote_state = 'deep_quote'
                        i += 1
                        continue
                    
                    if stripped_line:
                        top_quote_lines.append(stripped_line)
                        consecutive_empty = 0
                        in_paragraph = True
                    else:
                        # Empty line
                        consecutive_empty += 1
                        if in_paragraph:
                            # We were in a paragraph, now it ended
                            paragraphs_collected += 1
                            in_paragraph = False
                            
                            # Check if we've collected enough paragraphs
                            if paragraphs_collected >= max_top_quote_paragraphs:
                                if top_quote_lines:
                                    cleaned_lines.append('[Quoted head retained]')
                                    for qline in top_quote_lines:
                                        cleaned_lines.append(f'> {qline}')
                                    cleaned_lines.append('')
                                quote_state = 'deep_quote'
                                i += 1
                                continue
                        
                        # After 2 consecutive empty lines, also stop collecting
                        if consecutive_empty >= 2:
                            if top_quote_lines:
                                cleaned_lines.append('[Quoted head retained]')
                                for qline in top_quote_lines:
                                    cleaned_lines.append(f'> {qline}')
                                cleaned_lines.append('')
                            quote_state = 'deep_quote'
                            i += 1
                            continue
                    
                    i += 1
                    continue
                    
                elif quote_prefix_count > 1:
                    # Multi-level quote (> >), save collected and go to deep
                    if top_quote_lines:
                        cleaned_lines.append('[Quoted head retained]')
                        for qline in top_quote_lines:
                            cleaned_lines.append(f'> {qline}')
                        cleaned_lines.append('')
                    quote_state = 'deep_quote'
                    i += 1
                    continue
                    
                else:  # quote_prefix_count == 0
                    # No quote prefix, end of quote
                    if top_quote_lines:
                        cleaned_lines.append('[Quoted head retained]')
                        for qline in top_quote_lines:
                            cleaned_lines.append(f'> {qline}')
                        cleaned_lines.append('')
                    quote_state = None
                    seen_quote_header = False
                    # Don't skip this line, process it normally
                    if not is_quote_marker and line.strip():
                        cleaned_lines.append(line)
                    i += 1
                    continue
            
            elif quote_state == 'deep_quote':
                # Skip all lines until we're out of quote
                # In deep_quote, we skip everything - this handles -----Original Message----- case
                if quote_prefix_count == 0 and not is_quote_marker:
                    # Check if this line is quoted content metadata (From:, To:, Subject:, etc.)
                    if any(re.match(p, line.strip(), re.IGNORECASE) for p in [r'^From:', r'^To:', r'^Subject:', r'^Date:', r'^Sent:', r'^Received:', r'^От:', r'^Дата:', r'^Тема:', r'^Кому:', r'^Cc:']):
                        # Still in quoted metadata
                        i += 1
                        continue
                    
                    # Check if line looks like an email or blank
                    if not line.strip():
                        # Empty line in deep quote, continue skipping
                        i += 1
                        continue
                    
                    # Non-metadata, non-empty line with no > prefix
                    # Check if this could be quoted body content or end of quote
                    # Heuristic: if we recently saw metadata headers, this is likely still quote body
                    # For now, remain conservative and exit quote on substantial non-metadata content
                    # But skip if it looks like forwarded content
                    if any(keyword in line.lower() for keyword in ['thanks', 'regards', 'best', 'спасибо', 'уважением']):
                        # Likely signature within quote, keep skipping
                        i += 1
                        continue
                    
                    # For -----Original Message----- case, everything after it should be skipped
                    # We'll need better detection - for now, be aggressive and stay in deep_quote
                    # unless we see clear new content markers
                    
                    # If line is very short (< 5 words) or looks like continuation, skip it
                    word_count = len(line.split())
                    if word_count < 10:
                        i += 1
                        continue
                    
                    # Longer line without metadata - exit quote
                    quote_state = None
                    seen_quote_header = False
                    if line.strip():
                        cleaned_lines.append(line)
                i += 1
                continue
            
            else:  # quote_state is None
                if is_quote_marker:
                    # Start of deep quote
                    quote_state = 'deep_quote'
                    i += 1
                    continue
                elif quote_prefix_count > 0:
                    # Orphan > line without header, treat as deep quote
                    quote_state = 'deep_quote'
                    i += 1
                    continue
                else:
                    # Regular line
                    cleaned_lines.append(line)
                    i += 1
                    continue
        
        # Handle case where email ends while still collecting top quote
        if quote_state == 'collecting_top' and top_quote_lines:
            cleaned_lines.append('[Quoted head retained]')
            for qline in top_quote_lines:
                cleaned_lines.append(f'> {qline}')
        
        return '\n'.join(cleaned_lines)
    
    def _remove_all_quotes(self, text: str, max_levels: int = 5) -> str:
        """Remove all quoted text (legacy behavior)."""
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
