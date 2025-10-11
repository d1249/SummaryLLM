"""
Context selection for relevant evidence chunks.
"""
import re
from typing import List
import structlog

from digest_core.evidence.split import EvidenceChunk

logger = structlog.get_logger()


class ContextSelector:
    """Select relevant evidence chunks based on heuristics."""
    
    def __init__(self):
        # Positive signals (actionable content)
        self.positive_patterns = [
            r'\b(please|пожалуйста|need|нужно|required|требуется)\b',
            r'\b(approve|одобрить|review|проверить|complete|завершить)\b',
            r'\b(urgent|срочно|asap|deadline|срок|due|до)\b',
            r'\b(meeting|встреча|call|звонок|schedule|запланировать)\b',
            r'\b(action|действие|task|задача|assignment|поручение)\b',
            r'\b(confirm|подтвердить|respond|ответить|reply|ответ)\b',
        ]
        
        # Negative signals (non-actionable content)
        self.negative_patterns = [
            r'\b(fyi|for your information|к сведению)\b',
            r'\b(newsletter|рассылка|digest|дайджест)\b',
            r'\b(automated|автоматический|system|система)\b',
            r'\b(no action required|действие не требуется)\b',
            r'\b(information only|только информация)\b',
        ]
        
        # Service email patterns
        self.service_patterns = [
            r'\b(auto-submitted|автоответ)\b',
            r'\b(undeliverable|недоставлено)\b',
            r'\b(postmaster@|noreply@|no-reply@)\b',
            r'\b(delivery status|статус доставки)\b',
            r'\b(out of office|вне офиса)\b',
        ]
        
        # Compile patterns
        self.positive_regex = re.compile('|'.join(self.positive_patterns), re.IGNORECASE)
        self.negative_regex = re.compile('|'.join(self.negative_patterns), re.IGNORECASE)
        self.service_regex = re.compile('|'.join(self.service_patterns), re.IGNORECASE)
    
    def select_context(self, evidence_chunks: List[EvidenceChunk]) -> List[EvidenceChunk]:
        """Select relevant evidence chunks for LLM processing."""
        logger.info("Selecting context from evidence", total_chunks=len(evidence_chunks))
        
        # Filter out service emails first
        filtered_chunks = self._filter_service_emails(evidence_chunks)
        
        # Score chunks based on relevance
        scored_chunks = self._score_chunks(filtered_chunks)
        
        # Select top chunks based on score
        selected_chunks = self._select_top_chunks(scored_chunks)
        
        logger.info("Context selection completed", 
                   original_chunks=len(evidence_chunks),
                   filtered_chunks=len(filtered_chunks),
                   selected_chunks=len(selected_chunks))
        
        return selected_chunks
    
    def _filter_service_emails(self, chunks: List[EvidenceChunk]) -> List[EvidenceChunk]:
        """Filter out service emails and automated responses."""
        filtered_chunks = []
        
        for chunk in chunks:
            # Check for service email patterns
            if self.service_regex.search(chunk.content):
                logger.debug("Filtered service email", evidence_id=chunk.evidence_id)
                continue
            
            # Check for auto-submitted headers in source
            if chunk.source_ref.get('type') == 'email':
                # Additional filtering could be done here based on email headers
                pass
            
            filtered_chunks.append(chunk)
        
        return filtered_chunks
    
    def _score_chunks(self, chunks: List[EvidenceChunk]) -> List[EvidenceChunk]:
        """Score chunks based on relevance heuristics."""
        scored_chunks = []
        
        for chunk in chunks:
            score = chunk.priority_score  # Start with existing priority score
            
            # Add positive signals
            positive_matches = len(self.positive_regex.findall(chunk.content))
            score += positive_matches * 1.0
            
            # Subtract negative signals
            negative_matches = len(self.negative_regex.findall(chunk.content))
            score -= negative_matches * 0.5
            
            # Boost score for direct address patterns
            direct_address_score = self._calculate_direct_address_score(chunk.content)
            score += direct_address_score
            
            # Boost score for deadline/date patterns
            deadline_score = self._calculate_deadline_score(chunk.content)
            score += deadline_score
            
            # Create updated chunk with new score
            updated_chunk = chunk._replace(priority_score=score)
            scored_chunks.append(updated_chunk)
        
        return scored_chunks
    
    def _calculate_direct_address_score(self, content: str) -> float:
        """Calculate score for direct address patterns."""
        score = 0.0
        
        # Direct address patterns
        direct_patterns = [
            r'\b(you|вы|ты)\b.*\b(need|нужно|should|должны|must|должны)\b',
            r'\b(can you|можете ли вы|could you|не могли бы вы)\b',
            r'\b(please|пожалуйста).*\b(you|вы)\b',
            r'\b(urgent|срочно).*\b(you|вы)\b',
        ]
        
        for pattern in direct_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score += 1.0
        
        return score
    
    def _calculate_deadline_score(self, content: str) -> float:
        """Calculate score for deadline and date patterns."""
        score = 0.0
        
        # Date patterns
        date_patterns = [
            r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b',  # DD/MM/YYYY
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b(today|tomorrow|yesterday|сегодня|завтра|вчера)\b',
            r'\b(this week|next week|эта неделя|следующая неделя)\b',
            r'\b(end of|конец)\b.*\b(week|month|недели|месяца)\b',
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score += 0.5
        
        # Deadline patterns
        deadline_patterns = [
            r'\b(deadline|срок|due|до)\b',
            r'\b(by|к)\b.*\b(end of|концу)\b',
            r'\b(urgent|срочно)\b',
            r'\b(asap|as soon as possible|как можно скорее)\b',
        ]
        
        for pattern in deadline_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score += 0.8
        
        return score
    
    def _select_top_chunks(self, scored_chunks: List[EvidenceChunk], max_chunks: int = 20) -> List[EvidenceChunk]:
        """Select top chunks based on score."""
        # Sort by score (highest first)
        sorted_chunks = sorted(scored_chunks, key=lambda c: c.priority_score, reverse=True)
        
        # Take top chunks
        selected_chunks = sorted_chunks[:max_chunks]
        
        # Ensure we have at least some chunks if available
        if not selected_chunks and scored_chunks:
            # Take chunks with positive scores
            positive_chunks = [c for c in scored_chunks if c.priority_score > 0]
            if positive_chunks:
                selected_chunks = positive_chunks[:max_chunks]
            else:
                # Take top chunks regardless of score
                selected_chunks = sorted_chunks[:min(5, len(sorted_chunks))]
        
        return selected_chunks
    
    def filter_by_recipient_type(self, chunks: List[EvidenceChunk], user_email: str) -> List[EvidenceChunk]:
        """Filter chunks based on recipient type (To vs CC)."""
        # This would require access to the original message data
        # For now, we'll implement a simplified version
        
        # In a real implementation, you would:
        # 1. Look up the original message for each chunk
        # 2. Check if user_email is in To vs CC recipients
        # 3. Boost priority for To recipients
        
        logger.info("Recipient filtering applied", user_email=user_email)
        return chunks
