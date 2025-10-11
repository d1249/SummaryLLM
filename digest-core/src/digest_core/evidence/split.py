"""
Evidence splitting for LLM processing.
"""
import uuid
from typing import List, NamedTuple, Dict, Any
from datetime import datetime
import structlog

from digest_core.threads.build import ConversationThread

logger = structlog.get_logger()


class EvidenceChunk(NamedTuple):
    """A chunk of evidence for LLM processing."""
    evidence_id: str
    conversation_id: str
    content: str
    source_ref: Dict[str, Any]
    token_count: int
    priority_score: float


class EvidenceSplitter:
    """Split conversation threads into evidence chunks for LLM processing."""
    
    def __init__(self):
        self.max_tokens_per_chunk = 512
        self.min_tokens_per_chunk = 64
        self.max_chunks_per_message = 12
        self.max_total_tokens = 3000  # Total budget per LLM call
        
    def split_evidence(self, threads: List[ConversationThread]) -> List[EvidenceChunk]:
        """Split threads into evidence chunks."""
        logger.info("Splitting evidence from threads", thread_count=len(threads))
        
        all_chunks = []
        
        for thread in threads:
            try:
                chunks = self._split_thread_evidence(thread)
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
    
    def _split_thread_evidence(self, thread: ConversationThread) -> List[EvidenceChunk]:
        """Split a single thread into evidence chunks."""
        chunks = []
        
        # Process each message in the thread
        for i, message in enumerate(thread.messages):
            message_chunks = self._split_message_content(message, thread.conversation_id, i)
            chunks.extend(message_chunks)
        
        return chunks
    
    def _split_message_content(self, message, conversation_id: str, message_index: int) -> List[EvidenceChunk]:
        """Split a single message into chunks."""
        chunks = []
        
        # Clean and prepare content
        content = message.text_body.strip()
        if not content:
            return chunks
        
        # Split by paragraphs first
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        current_chunk = ""
        chunk_count = 0
        
        for paragraph in paragraphs:
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            paragraph_tokens = len(paragraph) // 4
            
            # If adding this paragraph would exceed max tokens, finalize current chunk
            if (len(current_chunk) // 4) + paragraph_tokens > self.max_tokens_per_chunk:
                if current_chunk and (len(current_chunk) // 4) >= self.min_tokens_per_chunk:
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
            
            # Limit chunks per message
            if chunk_count >= self.max_chunks_per_message:
                break
        
        # Add final chunk if it exists
        if current_chunk and (len(current_chunk) // 4) >= self.min_tokens_per_chunk:
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
        token_count = len(content) // 4  # Rough token estimation
        
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
        
        return EvidenceChunk(
            evidence_id=evidence_id,
            conversation_id=conversation_id,
            content=content,
            source_ref=source_ref,
            token_count=token_count,
            priority_score=priority_score
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
