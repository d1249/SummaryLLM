"""
Context selection for relevant evidence chunks using balanced bucket strategy.
"""
import re
from typing import List, Dict
from datetime import datetime, timezone
from collections import defaultdict
import structlog

from digest_core.evidence.split import EvidenceChunk
from digest_core.config import SelectionBucketsConfig, SelectionWeightsConfig, ContextBudgetConfig, ShrinkConfig

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
        # NEW: Auto-shrink metrics
        self.budget_requested = 0
        self.budget_applied = 0
        self.shrinks_count = 0
        self.shrink_percentage = 0.0
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary."""
        return {
            "covered_threads": len(self.covered_threads),
            "selected_by_bucket": dict(self.selected_by_bucket),
            "discarded_action_like": self.discarded_action_like,
            "token_budget_used": self.token_budget_used,
            "total_chunks_considered": self.total_chunks_considered,
            "budget_requested": self.budget_requested,
            "budget_applied": self.budget_applied,
            "shrinks_count": self.shrinks_count,
            "shrink_percentage": self.shrink_percentage
        }


class ContextSelector:
    """Select relevant evidence chunks using balanced bucket strategy."""
    
    def __init__(self, buckets_config: SelectionBucketsConfig = None, weights_config: SelectionWeightsConfig = None,
                 context_budget_config: ContextBudgetConfig = None, shrink_config: ShrinkConfig = None):
        self.buckets_config = buckets_config or SelectionBucketsConfig()
        self.weights_config = weights_config or SelectionWeightsConfig()
        self.context_budget_config = context_budget_config or ContextBudgetConfig()
        self.shrink_config = shrink_config or ShrinkConfig()
        
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
        
        # Step 3: Auto-shrink if enabled and over budget
        max_tokens = self.context_budget_config.max_total_tokens
        if self.shrink_config.enable_auto_shrink:
            selected_chunks = self._ensure_token_budget(selected_chunks, max_tokens)
            
            # Calculate shrink percentage
            if self.metrics.budget_requested > 0:
                self.metrics.shrink_percentage = (
                    (self.metrics.budget_requested - self.metrics.budget_applied) / 
                    self.metrics.budget_requested * 100.0
                )
        
        # Update final token budget used
        self.metrics.token_budget_used = sum(c.token_count for c in selected_chunks)
        
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
    
    def _ensure_token_budget(self, selected: List[EvidenceChunk], 
                            max_tokens: int) -> List[EvidenceChunk]:
        """
        Auto-shrink selected chunks to fit budget while preserving minimum quotas.
        
        Shrink order:
        1. Remove remainder (non-bucket) chunks with low score
        2. Deduplicate chunks exceeding per_thread_max
        3. Remove chunks from buckets exceeding minimum quotas (low priority first):
           - critical_senders
           - dates_deadlines
           - addressed_to_me
           - threads_top (highest priority, protected)
        4. If still over budget, remove globally lowest scored while keeping min quotas
        """
        self.metrics.budget_requested = sum(c.token_count for c in selected)
        
        if self.metrics.budget_requested <= max_tokens:
            self.metrics.budget_applied = self.metrics.budget_requested
            return selected
        
        logger.info("Token budget exceeded, applying auto-shrink",
                   requested=self.metrics.budget_requested,
                   max_tokens=max_tokens)
        
        # Track which chunks belong to which bucket
        chunk_to_bucket = {}
        for chunk in selected:
            bucket = self._get_chunk_bucket(chunk)
            chunk_to_bucket[id(chunk)] = bucket
        
        # Step 1: Remove remainder chunks with low score
        remainder_chunks = [c for c in selected if chunk_to_bucket[id(c)] == 'remainder']
        remainder_chunks.sort(key=lambda c: c.priority_score)
        
        kept = [c for c in selected if chunk_to_bucket[id(c)] != 'remainder']
        current_tokens = sum(c.token_count for c in kept)
        
        # Add back remainder chunks that fit
        for chunk in reversed(remainder_chunks):
            if current_tokens + chunk.token_count <= max_tokens:
                kept.append(chunk)
                current_tokens += chunk.token_count
            else:
                self.metrics.shrinks_count += 1
        
        if current_tokens <= max_tokens:
            self.metrics.budget_applied = current_tokens
            return kept
        
        # Step 2: Deduplicate over per_thread_max
        kept = self._deduplicate_over_thread_cap(kept, max_tokens)
        current_tokens = sum(c.token_count for c in kept)
        
        if current_tokens <= max_tokens:
            self.metrics.budget_applied = current_tokens
            return kept
        
        # Step 3: Shrink buckets over min quotas (priority order)
        if self.shrink_config.preserve_min_quotas:
            bucket_order = ['critical_senders', 'dates_deadlines', 'addressed_to_me']
            
            for bucket_name in bucket_order:
                min_quota = getattr(self.buckets_config, bucket_name)
                bucket_chunks = [c for c in kept if chunk_to_bucket[id(c)] == bucket_name]
                
                if len(bucket_chunks) > min_quota and current_tokens > max_tokens:
                    # Sort by score, keep min_quota best
                    bucket_chunks.sort(key=lambda c: c.priority_score, reverse=True)
                    to_keep = bucket_chunks[:min_quota]
                    to_remove = bucket_chunks[min_quota:]
                    
                    # Remove lowest scored over-quota chunks
                    to_remove.sort(key=lambda c: c.priority_score)
                    for chunk in to_remove:
                        if current_tokens > max_tokens:
                            kept.remove(chunk)
                            current_tokens -= chunk.token_count
                            self.metrics.shrinks_count += 1
                        else:
                            break
        
        # Step 4: Global low-score removal (preserve min quotas)
        if current_tokens > max_tokens:
            kept = self._global_shrink_preserve_quotas(kept, max_tokens, chunk_to_bucket)
            current_tokens = sum(c.token_count for c in kept)
        
        self.metrics.budget_applied = current_tokens
        logger.info("Auto-shrink completed",
                   removed=self.metrics.shrinks_count,
                   final_tokens=current_tokens)
        
        return kept
    
    def _get_chunk_bucket(self, chunk: EvidenceChunk) -> str:
        """Determine which bucket a chunk belongs to."""
        # Check critical_senders
        if chunk.signals.get('sender_rank', 1) >= 2:
            return 'critical_senders'
        
        # Check dates_deadlines
        if len(chunk.signals.get('dates', [])) > 0:
            return 'dates_deadlines'
        
        # Check addressed_to_me
        if chunk.addressed_to_me:
            return 'addressed_to_me'
        
        # Default to remainder
        return 'remainder'
    
    def _deduplicate_over_thread_cap(self, chunks: List[EvidenceChunk], 
                                     max_tokens: int) -> List[EvidenceChunk]:
        """Remove chunks exceeding per_thread_max, keeping highest scored."""
        thread_chunks = defaultdict(list)
        for chunk in chunks:
            thread_chunks[chunk.conversation_id].append(chunk)
        
        kept = []
        for conv_id, conv_chunks in thread_chunks.items():
            # Sort by score and keep up to per_thread_max
            conv_chunks.sort(key=lambda c: c.priority_score, reverse=True)
            max_per_thread = self.context_budget_config.per_thread_max
            
            for i, chunk in enumerate(conv_chunks):
                if i < max_per_thread:
                    kept.append(chunk)
                else:
                    self.metrics.shrinks_count += 1
        
        return kept
    
    def _global_shrink_preserve_quotas(self, chunks: List[EvidenceChunk], 
                                       max_tokens: int,
                                       chunk_to_bucket: Dict[int, str]) -> List[EvidenceChunk]:
        """Final shrink by removing lowest scored chunks while preserving min quotas."""
        # Count current bucket sizes
        bucket_counts = defaultdict(int)
        for chunk in chunks:
            bucket = chunk_to_bucket[id(chunk)]
            bucket_counts[bucket] += 1
        
        # Sort all chunks by score (lowest first for removal)
        chunks_sorted = sorted(chunks, key=lambda c: c.priority_score)
        
        current_tokens = sum(c.token_count for c in chunks)
        kept = list(chunks)
        
        for chunk in chunks_sorted:
            if current_tokens <= max_tokens:
                break
            
            bucket = chunk_to_bucket[id(chunk)]
            
            # Check if we can remove this chunk without violating min quota
            if bucket in ['threads_top', 'addressed_to_me', 'dates_deadlines', 'critical_senders']:
                min_quota = getattr(self.buckets_config, bucket)
                if bucket_counts[bucket] > min_quota:
                    kept.remove(chunk)
                    current_tokens -= chunk.token_count
                    bucket_counts[bucket] -= 1
                    self.metrics.shrinks_count += 1
            else:
                # Remainder bucket, can remove freely
                kept.remove(chunk)
                current_tokens -= chunk.token_count
                self.metrics.shrinks_count += 1
        
        return kept
