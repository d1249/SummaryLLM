"""
Markdown output assembler for digest data.
"""
from pathlib import Path
from typing import List
import structlog

from digest_core.llm.schemas import Digest

logger = structlog.get_logger()


class MarkdownAssembler:
    """Assemble digest data into Markdown output."""
    
    def __init__(self):
        self.max_words = 400
        self.max_items_per_section = 10
    
    def write_digest(self, digest_data: Digest, output_path: Path) -> None:
        """Write digest data to Markdown file."""
        logger.info("Writing Markdown digest", output_path=str(output_path))
        
        try:
            # Generate markdown content
            markdown_content = self._generate_markdown(digest_data)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info("Markdown digest written successfully", 
                       output_path=str(output_path),
                       word_count=self._count_words(markdown_content))
            
        except Exception as e:
            logger.error("Failed to write Markdown digest", 
                        output_path=str(output_path),
                        error=str(e))
            raise
    
    def _generate_markdown(self, digest_data: Digest) -> str:
        """Generate markdown content from digest data."""
        lines = []
        
        # Header
        lines.append(f"# Дайджест действий - {digest_data.digest_date}")
        lines.append("")
        lines.append(f"*Trace ID: {digest_data.trace_id}*")
        lines.append("")
        
        # Check if digest is empty
        total_items = sum(len(section.items) for section in digest_data.sections)
        if total_items == 0:
            lines.append("За период релевантных действий не найдено.")
            return "\n".join(lines)
        
        # Sections
        for section in digest_data.sections:
            if not section.items:
                continue
            
            lines.append(f"## {section.title}")
            lines.append("")
            
            # Limit items per section
            items_to_show = section.items[:self.max_items_per_section]
            
            for i, item in enumerate(items_to_show, 1):
                lines.append(f"### {i}. {item.title}")
                
                # Add due date if present
                if item.due:
                    lines.append(f"**Срок:** {item.due}")
                
                # Add confidence
                confidence_text = self._format_confidence(item.confidence)
                lines.append(f"**Уверенность:** {confidence_text}")
                
                # Add evidence reference
                lines.append(f"**Источник:** [Evidence {item.evidence_id}](#evidence-{item.evidence_id})")
                
                # Add owners if present
                if item.owners_masked:
                    owners_text = ", ".join(item.owners_masked)
                    lines.append(f"**Ответственные:** {owners_text}")
                
                lines.append("")
            
            # Add note if items were truncated
            if len(section.items) > self.max_items_per_section:
                remaining = len(section.items) - self.max_items_per_section
                lines.append(f"*... и еще {remaining} элементов*")
                lines.append("")
        
        # Evidence section
        lines.append("## Источники")
        lines.append("")
        
        evidence_ids = set()
        for section in digest_data.sections:
            for item in section.items:
                evidence_ids.add(item.evidence_id)
        
        for evidence_id in sorted(evidence_ids):
            lines.append(f"### Evidence {evidence_id}")
            lines.append(f"*ID: {evidence_id}*")
            lines.append("")
        
        # Check word count and truncate if necessary
        content = "\n".join(lines)
        word_count = self._count_words(content)
        
        if word_count > self.max_words:
            logger.warning("Markdown content exceeds word limit", 
                          word_count=word_count, 
                          max_words=self.max_words)
            content = self._truncate_content(content, self.max_words)
        
        return content
    
    def _format_confidence(self, confidence: float) -> str:
        """Format confidence score as text."""
        if confidence >= 0.9:
            return "Очень высокая"
        elif confidence >= 0.7:
            return "Высокая"
        elif confidence >= 0.5:
            return "Средняя"
        elif confidence >= 0.3:
            return "Низкая"
        else:
            return "Очень низкая"
    
    def _count_words(self, text: str) -> int:
        """Count words in text."""
        # Simple word counting (split by whitespace)
        words = text.split()
        return len(words)
    
    def _truncate_content(self, content: str, max_words: int) -> str:
        """Truncate content to fit word limit."""
        words = content.split()
        
        if len(words) <= max_words:
            return content
        
        # Truncate and add note
        truncated_words = words[:max_words - 10]  # Leave room for truncation note
        truncated_content = " ".join(truncated_words)
        
        # Add truncation note
        truncated_content += "\n\n*[Содержимое обрезано для соблюдения лимита слов]*"
        
        return truncated_content
    
    def generate_summary(self, digest_data: Digest) -> str:
        """Generate a brief summary of the digest."""
        total_items = sum(len(section.items) for section in digest_data.sections)
        
        if total_items == 0:
            return "За период релевантных действий не найдено."
        
        summary_parts = [f"Найдено {total_items} действий:"]
        
        for section in digest_data.sections:
            if section.items:
                summary_parts.append(f"- {section.title}: {len(section.items)}")
        
        return " ".join(summary_parts)
    
    def validate_markdown(self, content: str) -> bool:
        """Validate markdown content structure."""
        try:
            lines = content.split('\n')
            
            # Check for header
            if not any(line.startswith('# ') for line in lines):
                return False
            
            # Check for sections
            if not any(line.startswith('## ') for line in lines):
                return False
            
            return True
            
        except Exception as e:
            logger.warning("Markdown validation failed", error=str(e))
            return False
