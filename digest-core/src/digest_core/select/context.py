"""
Context selection for relevant evidence chunks using balanced bucket strategy.
"""
import re
from typing import List, Dict
from datetime import datetime, timezone
from collections import defaultdict
import structlog

from digest_core.evidence.split import EvidenceChunk
from digest_core.config import SelectionBucketsConfig, SelectionWeightsConfig

try:
    import dateutil.parser
except ImportError:
    dateutil = None

logger = structlog.get_logger()


class SelectionMetrics:
    """Metrics for evidence selection process."""
    
    def __init__(self):
        self.covered_threads = set()
        self.selected_by_bucket = defaultdict(int)
        self.discarded_action_like = 0
        self.token_budget_used = 0
        self.total_chunks_considered = 0
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary."""
        return {
            "covered_threads": len(self.covered_threads),
            "selected_by_bucket": dict(self.selected_by_bucket),
            "discarded_action_like": self.discarded_action_like,
            "token_budget_used": self.token_budget_used,
            "total_chunks_considered": self.total_chunks_considered
        }


class ContextSelector:
    """Select relevant evidence chunks using balanced bucket strategy."""
    
    def __init__(self, buckets_config: SelectionBucketsConfig = None, weights_config: SelectionWeightsConfig = None):
        self.buckets_config = buckets_config or SelectionBucketsConfig()
        self.weights_config = weights_config or SelectionWeightsConfig()
        
        # Negative patterns (noreply, unsubscribe, etc.)
        self.negative_patterns = [
            r'\b(noreply@|no-reply@|donotreply@)\b',
            r'\b(unsubscribe|отписаться)\b',
            r'\b(auto-submitted|автоответ)\b',
            r'\b(postmaster@)\b',
            r'\b(delivery status|статус доставки)\b',
        ]
        self.negative_regex = re.compile('|'.join(self.negative_patterns), re.IGNORECASE)
        
        # Document attachment types
        self.doc_attachment_types = {'pdf', 'doc', 'docx', 'xlsx', 'xls', 'ppt', 'pptx'}
        
        # Metrics
        self.metrics = SelectionMetrics()
    
    def select_context(self, evidence_chunks: List[EvidenceChunk]) -> List[EvidenceChunk]:
        """
        Select relevant evidence chunks using balanced bucket strategy.
        
        Buckets:
        - threads_top: ≥10 threads by recency/volume (1 chunk each)
        - addressed_to_me: ≥8 chunks with AddressedToMe=true
        - dates_deadlines: ≥6 chunks with dates/deadlines
        - critical_senders: ≥4 chunks from sender_rank>=2
        - remainder: general scoring
        """
        logger.info("Starting balanced context selection", total_chunks=len(evidence_chunks))
        
        self.metrics = SelectionMetrics()
        self.metrics.total_chunks_considered = len(evidence_chunks)
        
        # Step 1: Enhanced scoring for all chunks
        scored_chunks = self._calculate_enhanced_scores(evidence_chunks)
        
        # Step 2: Balanced bucket selection
        selected_chunks = self._select_with_buckets(scored_chunks)
        
        # Log metrics
        logger.info("Context selection completed", 
                   **self.metrics.to_dict(),
                   selected_chunks=len(selected_chunks))
        
        return selected_chunks
    
    def _calculate_enhanced_scores(self, chunks: List[EvidenceChunk]) -> List[EvidenceChunk]:
        """Calculate enhanced scores for all chunks using configured weights."""
        scored_chunks = []
        
        for chunk in chunks:
            score = 0.0
            
            # 1. Recency (затухание по времени)
            recency_score = self._calculate_recency_score(chunk)
            score += recency_score * self.weights_config.recency
            
            # 2. AddressedToMe
            if chunk.addressed_to_me:
                score += self.weights_config.addressed_to_me
            
            # 3. Action verbs
            action_verbs = chunk.signals.get('action_verbs', [])
            score += len(action_verbs) * self.weights_config.action_verbs
            
            # 4. Question mark
            if chunk.signals.get('contains_question', False):
                score += self.weights_config.question_mark
            
            # 5. Dates found
            dates = chunk.signals.get('dates', [])
            score += len(dates) * self.weights_config.dates_found
            
            # 6. Importance
            importance = chunk.message_metadata.get('importance', 'Normal')
            if importance == 'High':
                score += self.weights_config.importance_high
            
            # 7. Flagged
            if chunk.message_metadata.get('is_flagged', False):
                score += self.weights_config.is_flagged
            
            # 8. Document attachments
            if self._has_doc_attachments(chunk):
                score += self.weights_config.has_doc_attachments
            
            # 9. Sender rank
            sender_rank = chunk.signals.get('sender_rank', 1)
            score += sender_rank * self.weights_config.sender_rank
            
            # 10. Thread activity (from priority_score - includes recency and other signals)
            # Use as baseline but don't double-count
            score += chunk.priority_score * 0.1  # Small contribution to not lose original scoring
            
            # 11. Negative priors (penalty)
            if self._has_negative_prior(chunk):
                score += self.weights_config.negative_prior  # This is negative
            
            # Update chunk with new score
            updated_chunk = chunk._replace(priority_score=score)
            scored_chunks.append(updated_chunk)
        
        return scored_chunks
    
    def _calculate_recency_score(self, chunk: EvidenceChunk) -> float:
        """
        Calculate recency score with exponential decay.
        
        Score decreases as message gets older:
        - < 1 hour: 1.0
        - 1-6 hours: 0.8
        - 6-24 hours: 0.5
        - > 24 hours: 0.2
        """
        received_at = chunk.message_metadata.get('received_at', '')
        if not received_at:
            return 0.2
        
        try:
            # Parse ISO datetime
            if dateutil:
                msg_time = dateutil.parser.isoparse(received_at)
            else:
                # Fallback to standard datetime parsing
                msg_time = datetime.fromisoformat(received_at.replace('Z', '+00:00'))
            
            # Calculate hours ago
            now = datetime.now(timezone.utc)
            hours_ago = (now - msg_time.astimezone(timezone.utc)).total_seconds() / 3600
            
            if hours_ago < 1:
                return 1.0
            elif hours_ago < 6:
                return 0.8
            elif hours_ago < 24:
                return 0.5
            else:
                return 0.2
        except Exception:
            return 0.2
    
    def _has_doc_attachments(self, chunk: EvidenceChunk) -> bool:
        """Check if chunk has document attachments (pdf, doc, xlsx, etc.)."""
        attachment_types = chunk.message_metadata.get('attachment_types', [])
        return any(ext.lower() in self.doc_attachment_types for ext in attachment_types)
    
    def _has_negative_prior(self, chunk: EvidenceChunk) -> bool:
        """Check for negative priors (noreply, unsubscribe, etc.)."""
        # Check sender email
        sender = chunk.message_metadata.get('from', '')
        if self.negative_regex.search(sender):
            return True
        
        # Check content
        if self.negative_regex.search(chunk.content):
            return True
        
        return False
    
    def _select_with_buckets(self, scored_chunks: List[EvidenceChunk]) -> List[EvidenceChunk]:
        """
        Select chunks using balanced bucket strategy with token budget protection.
        
        Returns list of selected chunks.
        """
        selected = []
        thread_chunk_counts = defaultdict(int)
        remaining_budget = 3000  # Token budget
        
        # Sort all chunks by score (highest first)
        all_sorted = sorted(scored_chunks, key=lambda c: c.priority_score, reverse=True)
        
        # Bucket 1: threads_top - cover different threads (1 chunk each by default)
        threads_covered = set()
        for chunk in all_sorted:
            if len(threads_covered) >= self.buckets_config.threads_top:
                break
            
            conv_id = chunk.conversation_id
            if conv_id in threads_covered:
                continue
            
            if remaining_budget >= chunk.token_count:
                selected.append(chunk)
                threads_covered.add(conv_id)
                thread_chunk_counts[conv_id] += 1
                remaining_budget -= chunk.token_count
                self.metrics.covered_threads.add(conv_id)
                self.metrics.selected_by_bucket['threads_top'] += 1
        
        # Bucket 2: addressed_to_me - chunks addressed to user
        addressed_chunks = [c for c in all_sorted if c.addressed_to_me and c not in selected]
        addressed_chunks = sorted(addressed_chunks, key=lambda c: c.priority_score, reverse=True)
        
        for chunk in addressed_chunks:
            if self.metrics.selected_by_bucket['addressed_to_me'] >= self.buckets_config.addressed_to_me:
                break
            
            conv_id = chunk.conversation_id
            if thread_chunk_counts[conv_id] >= self.buckets_config.per_thread_max:
                continue
            
            if remaining_budget >= chunk.token_count:
                selected.append(chunk)
                thread_chunk_counts[conv_id] += 1
                remaining_budget -= chunk.token_count
                self.metrics.covered_threads.add(conv_id)
                self.metrics.selected_by_bucket['addressed_to_me'] += 1
        
        # Bucket 3: dates_deadlines - chunks with dates/deadlines
        date_chunks = [c for c in all_sorted 
                      if len(c.signals.get('dates', [])) > 0 and c not in selected]
        date_chunks = sorted(date_chunks, key=lambda c: c.priority_score, reverse=True)
        
        for chunk in date_chunks:
            if self.metrics.selected_by_bucket['dates_deadlines'] >= self.buckets_config.dates_deadlines:
                break
            
            conv_id = chunk.conversation_id
            if thread_chunk_counts[conv_id] >= self.buckets_config.per_thread_max:
                continue
            
            if remaining_budget >= chunk.token_count:
                selected.append(chunk)
                thread_chunk_counts[conv_id] += 1
                remaining_budget -= chunk.token_count
                self.metrics.covered_threads.add(conv_id)
                self.metrics.selected_by_bucket['dates_deadlines'] += 1
        
        # Bucket 4: critical_senders - chunks from important senders (rank >= 2)
        critical_chunks = [c for c in all_sorted 
                          if c.signals.get('sender_rank', 1) >= 2 and c not in selected]
        critical_chunks = sorted(critical_chunks, key=lambda c: c.priority_score, reverse=True)
        
        for chunk in critical_chunks:
            if self.metrics.selected_by_bucket['critical_senders'] >= self.buckets_config.critical_senders:
                break
            
            conv_id = chunk.conversation_id
            if thread_chunk_counts[conv_id] >= self.buckets_config.per_thread_max:
                continue
            
            if remaining_budget >= chunk.token_count:
                selected.append(chunk)
                thread_chunk_counts[conv_id] += 1
                remaining_budget -= chunk.token_count
                self.metrics.covered_threads.add(conv_id)
                self.metrics.selected_by_bucket['critical_senders'] += 1
        
        # Bucket 5: remainder - fill up to max_total_chunks with general scoring
        remainder_chunks = [c for c in all_sorted if c not in selected]
        remainder_chunks = sorted(remainder_chunks, key=lambda c: c.priority_score, reverse=True)
        
        for chunk in remainder_chunks:
            if len(selected) >= self.buckets_config.max_total_chunks:
                break
            
            conv_id = chunk.conversation_id
            if thread_chunk_counts[conv_id] >= self.buckets_config.per_thread_max:
                continue
            
            if remaining_budget >= chunk.token_count:
                selected.append(chunk)
                thread_chunk_counts[conv_id] += 1
                remaining_budget -= chunk.token_count
                self.metrics.covered_threads.add(conv_id)
                self.metrics.selected_by_bucket['remainder'] += 1
        
        # Track discarded action-like chunks
        for chunk in scored_chunks:
            if chunk not in selected:
                action_verbs = chunk.signals.get('action_verbs', [])
                dates = chunk.signals.get('dates', [])
                if len(action_verbs) > 0 or len(dates) > 0 or chunk.addressed_to_me:
                    self.metrics.discarded_action_like += 1
        
        # Track token budget used
        self.metrics.token_budget_used = 3000 - remaining_budget
        
        return selected
    
    def get_metrics(self) -> Dict:
        """Get selection metrics."""
        return self.metrics.to_dict()
