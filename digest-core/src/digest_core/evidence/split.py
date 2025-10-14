"""
Evidence splitting for LLM processing.
"""
import re
import uuid
from typing import List, NamedTuple, Dict, Any
import structlog

from digest_core.threads.build import ConversationThread
from digest_core.evidence import signals
from digest_core.config import ContextBudgetConfig, ChunkingConfig

logger = structlog.get_logger()


class EvidenceChunk(NamedTuple):
    """A chunk of evidence for LLM processing."""
    evidence_id: str
    conversation_id: str
    content: str
    source_ref: Dict[str, Any]
    token_count: int
    priority_score: float
    message_metadata: Dict[str, Any]  # from, to, cc, subject, received_at, importance, flag, attachments
    addressed_to_me: bool
    user_aliases_matched: List[str]
    signals: Dict[str, Any]  # action_verbs, dates, contains_question, sender_rank, attachments


class EvidenceSplitter:
    """Split conversation threads into evidence chunks for LLM processing."""
    
    def __init__(self, user_aliases: List[str] = None, user_timezone: str = "Europe/Moscow",
                 context_budget_config: ContextBudgetConfig = None,
                 chunking_config: ChunkingConfig = None):
        self.max_tokens_per_chunk = 512
        self.min_tokens_per_chunk = 64
        self.context_budget_config = context_budget_config or ContextBudgetConfig()
        self.chunking_config = chunking_config or ChunkingConfig()
        self.max_total_tokens = self.context_budget_config.max_total_tokens
        self.user_aliases = user_aliases or []
        self.user_timezone = user_timezone
        
    def split_evidence(self, threads: List[ConversationThread], 
                      total_emails: int = 0, total_threads: int = 0) -> List[EvidenceChunk]:
        """Split threads into evidence chunks with adaptive chunking."""
        logger.info("Splitting evidence from threads", 
                   thread_count=len(threads),
                   total_emails=total_emails,
                   total_threads=total_threads)
        
        all_chunks = []
        
        for thread in threads:
            try:
                chunks = self._split_thread_evidence(thread, total_emails, total_threads)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning("Failed to split thread evidence", 
                             conversation_id=thread.conversation_id, error=str(e))
                continue
        
        # Sort chunks by priority score
        all_chunks.sort(key=lambda c: c.priority_score, reverse=True)
        
        # Limit total tokens
        limited_chunks = self._limit_total_tokens(all_chunks)
        
        logger.info("Evidence splitting completed", 
                   total_chunks=len(all_chunks),
                   limited_chunks=len(limited_chunks))
        
        return limited_chunks
    
    def _split_thread_evidence(self, thread: ConversationThread, 
                               total_emails: int = 0, total_threads: int = 0) -> List[EvidenceChunk]:
        """Split a single thread into evidence chunks."""
        chunks = []
        
        # Process each message in the thread
        for i, message in enumerate(thread.messages):
            message_chunks = self._split_message_content(
                message, thread.conversation_id, i, total_emails, total_threads)
            chunks.extend(message_chunks)
        
        return chunks
    
    def _detect_structural_breaks(self, text: str) -> List[int]:
        """
        Detect structural break points in text (headers, lists, separators).
        Returns list of line indices where breaks occur.
        """
        lines = text.split('\n')
        break_points = []
        
        for i, line in enumerate(lines):
            # Markdown headers
            if re.match(r'^#{1,3}\s+', line):
                break_points.append(i)
            # CAPS + colon (ЗАГОЛОВОК: / HEADER:)
            elif re.match(r'^[A-ZА-Я][A-ZА-Я\s]{3,}:\s*$', line):
                break_points.append(i)
            # Numbered lists
            elif re.match(r'^\s*\d+[\.)]\s+', line):
                break_points.append(i)
            # Email markers (On ... wrote:, От:, From:)
            elif re.match(r'^(On .+ wrote:|От:|From:|Subject:)', line, re.IGNORECASE):
                break_points.append(i)
            # Horizontal rules
            elif re.match(r'^[\-\*=]{3,}\s*$', line):
                break_points.append(i)
        
        return break_points
    
    def _split_message_content(self, message, conversation_id: str, message_index: int,
                               total_emails: int = 0, total_threads: int = 0) -> List[EvidenceChunk]:
        """Split message using adaptive chunking and structural boundaries."""
        chunks = []
        
        # Clean and prepare content
        content = message.text_body.strip()
        if not content:
            return chunks
        
        # Calculate adaptive max_chunks_per_message
        message_tokens = int(len(content.split()) * 1.3)
        
        if message_tokens > self.chunking_config.long_email_tokens:
            base_max = self.chunking_config.max_chunks_if_long
        else:
            base_max = self.chunking_config.max_chunks_default
        
        # Apply adaptive multiplier for high load
        if (total_emails >= self.chunking_config.adaptive_high_load_emails or 
            total_threads >= self.chunking_config.adaptive_high_load_threads):
            base_max = max(2, int(base_max * self.chunking_config.adaptive_multiplier))
        
        max_chunks_for_message = base_max
        
        # Detect structural breaks for better segmentation
        structural_breaks = self._detect_structural_breaks(content)
        
        # Split by paragraphs first (but respect structural breaks)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        current_chunk = ""
        chunk_count = 0
        
        for paragraph in paragraphs:
            # Estimate tokens (rough approximation: 1.3 tokens per word)
            paragraph_tokens = int(len(paragraph.split()) * 1.3)
            
            # If adding this paragraph would exceed max tokens, finalize current chunk
            current_chunk_tokens = int(len(current_chunk.split()) * 1.3)
            if current_chunk_tokens + paragraph_tokens > self.max_tokens_per_chunk:
                if current_chunk and current_chunk_tokens >= self.min_tokens_per_chunk:
                    chunk = self._create_evidence_chunk(
                        current_chunk, conversation_id, message, message_index, chunk_count
                    )
                    chunks.append(chunk)
                    chunk_count += 1
                    current_chunk = ""
                
                # If single paragraph is too long, split by sentences
                if paragraph_tokens > self.max_tokens_per_chunk:
                    sentence_chunks = self._split_by_sentences(paragraph, conversation_id, message, message_index, chunk_count)
                    chunks.extend(sentence_chunks)
                    chunk_count += len(sentence_chunks)
                else:
                    current_chunk = paragraph
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
            
            # Limit chunks per message (adaptive)
            if chunk_count >= max_chunks_for_message:
                break
        
        # Add final chunk if it exists
        final_chunk_tokens = int(len(current_chunk.split()) * 1.3)
        if current_chunk and final_chunk_tokens >= self.min_tokens_per_chunk:
            chunk = self._create_evidence_chunk(
                current_chunk, conversation_id, message, message_index, chunk_count
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_by_sentences(self, text: str, conversation_id: str, message, message_index: int, start_chunk_count: int) -> List[EvidenceChunk]:
        """Split long text by sentences."""
        import re
        
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = ""
        chunk_count = start_chunk_count
        
        for sentence in sentences:
            sentence_tokens = len(sentence) // 4
            
            if (len(current_chunk) // 4) + sentence_tokens > self.max_tokens_per_chunk:
                if current_chunk and (len(current_chunk) // 4) >= self.min_tokens_per_chunk:
                    chunk = self._create_evidence_chunk(
                        current_chunk, conversation_id, message, message_index, chunk_count
                    )
                    chunks.append(chunk)
                    chunk_count += 1
                    current_chunk = ""
                
                # If single sentence is still too long, truncate it
                if sentence_tokens > self.max_tokens_per_chunk:
                    truncated = sentence[:self.max_tokens_per_chunk * 4]
                    chunk = self._create_evidence_chunk(
                        truncated, conversation_id, message, message_index, chunk_count
                    )
                    chunks.append(chunk)
                    chunk_count += 1
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ". " + sentence
                else:
                    current_chunk = sentence
        
        # Add final chunk
        if current_chunk and (len(current_chunk) // 4) >= self.min_tokens_per_chunk:
            chunk = self._create_evidence_chunk(
                current_chunk, conversation_id, message, message_index, chunk_count
            )
            chunks.append(chunk)
        
        return chunks
    
    def _create_evidence_chunk(self, content: str, conversation_id: str, message, message_index: int, chunk_index: int) -> EvidenceChunk:
        """Create an evidence chunk from content."""
        evidence_id = str(uuid.uuid4())
        token_count = int(len(content.split()) * 1.3)  # Token estimation: 1.3 tokens per word
        
        # Calculate priority score based on content characteristics
        priority_score = self._calculate_priority_score(content, message)
        
        # Create source reference
        source_ref = {
            "type": "email",
            "msg_id": message.msg_id,
            "conversation_id": conversation_id,
            "message_index": message_index,
            "chunk_index": chunk_index
        }
        
        # Build message metadata
        message_metadata = {
            "from": message.sender_email,
            "to": message.to_recipients,
            "cc": message.cc_recipients,
            "subject": message.subject,
            "received_at": signals.normalize_datetime_to_tz(message.datetime_received, self.user_timezone),
            "importance": message.importance if hasattr(message, 'importance') else "Normal",
            "is_flagged": message.is_flagged if hasattr(message, 'is_flagged') else False,
            "has_attachments": message.has_attachments if hasattr(message, 'has_attachments') else False,
            "attachment_types": message.attachment_types if hasattr(message, 'attachment_types') else []
        }
        
        # Check if addressed to me
        addressed_to_me = False
        user_aliases_matched = []
        all_recipients = message.to_recipients + message.cc_recipients
        for alias in self.user_aliases:
            alias_lower = alias.lower()
            if alias_lower in [r.lower() for r in all_recipients]:
                addressed_to_me = True
                user_aliases_matched.append(alias)
        
        # Extract signals from content
        action_verbs = signals.extract_action_verbs(content)
        dates = signals.extract_dates(content)
        has_question = signals.contains_question(content)
        sender_rank = signals.calculate_sender_rank(message.sender_email)
        
        chunk_signals = {
            "action_verbs": action_verbs,
            "dates": dates,
            "contains_question": has_question,
            "sender_rank": sender_rank,
            "attachments": message_metadata["attachment_types"]
        }
        
        return EvidenceChunk(
            evidence_id=evidence_id,
            conversation_id=conversation_id,
            content=content,
            source_ref=source_ref,
            token_count=token_count,
            priority_score=priority_score,
            message_metadata=message_metadata,
            addressed_to_me=addressed_to_me,
            user_aliases_matched=user_aliases_matched,
            signals=chunk_signals
        )
    
    def _calculate_priority_score(self, content: str, message) -> float:
        """Calculate priority score for evidence chunk."""
        score = 0.0
        
        # Imperative verbs and action words
        action_words = [
            'please', 'пожалуйста', 'need', 'нужно', 'required', 'требуется',
            'approve', 'одобрить', 'review', 'проверить', 'complete', 'завершить',
            'urgent', 'срочно', 'asap', 'deadline', 'срок', 'due', 'до'
        ]
        
        content_lower = content.lower()
        for word in action_words:
            if word in content_lower:
                score += 1.0
        
        # Date/time references
        import re
        date_patterns = [
            r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b',  # DD/MM/YYYY
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b(today|tomorrow|yesterday|сегодня|завтра|вчера)\b'
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, content_lower):
                score += 0.5
        
        # Question marks indicate requests
        if '?' in content:
            score += 0.5
        
        # Exclamation marks indicate urgency
        if '!' in content:
            score += 0.3
        
        # Recent messages get higher priority
        from datetime import datetime, timezone
        hours_ago = (datetime.now(timezone.utc) - message.datetime_received).total_seconds() / 3600
        if hours_ago < 1:
            score += 2.0
        elif hours_ago < 6:
            score += 1.0
        elif hours_ago < 24:
            score += 0.5
        
        return score
    
    def _limit_total_tokens(self, chunks: List[EvidenceChunk]) -> List[EvidenceChunk]:
        """Limit total tokens across all chunks."""
        limited_chunks = []
        total_tokens = 0
        
        for chunk in chunks:
            if total_tokens + chunk.token_count <= self.max_total_tokens:
                limited_chunks.append(chunk)
                total_tokens += chunk.token_count
            else:
                # Try to fit a partial chunk if there's remaining budget
                remaining_tokens = self.max_total_tokens - total_tokens
                if remaining_tokens >= self.min_tokens_per_chunk:
                    # Truncate chunk to fit remaining budget
                    truncated_content = chunk.content[:remaining_tokens * 4]
                    truncated_chunk = chunk._replace(
                        content=truncated_content,
                        token_count=remaining_tokens
                    )
                    limited_chunks.append(truncated_chunk)
                break
        
        logger.info("Token budget applied", 
                   original_chunks=len(chunks),
                   limited_chunks=len(limited_chunks),
                   total_tokens=total_tokens)
        
        return limited_chunks
