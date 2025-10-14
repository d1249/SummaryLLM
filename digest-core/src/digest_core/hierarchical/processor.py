"""
Hierarchical processor for large-scale digest generation.

Implements two-stage processing:
1. Per-thread summarization (parallel)
2. Final aggregation to EnhancedDigest v2
"""
import json
import time
from typing import List, Dict, Any
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
import structlog
from jinja2 import Environment, FileSystemLoader

from digest_core.config import HierarchicalConfig
from digest_core.threads.build import ConversationThread
from digest_core.evidence.split import EvidenceChunk
from digest_core.llm.schemas import ThreadSummary, EnhancedDigest
from digest_core.llm.gateway import LLMGateway
from digest_core.hierarchical.metrics import HierarchicalMetrics

logger = structlog.get_logger()


class HierarchicalProcessor:
    """Process digest hierarchically: per-thread summaries → final aggregation."""
    
    def __init__(self, config: HierarchicalConfig, llm_gateway: LLMGateway):
        """
        Initialize hierarchical processor.
        
        Args:
            config: Hierarchical configuration
            llm_gateway: LLM gateway for API calls
        """
        self.config = config
        self.llm_gateway = llm_gateway
        self.metrics = HierarchicalMetrics()
    
    def should_use_hierarchical(self, threads: List, emails: List) -> bool:
        """
        Determine if hierarchical mode should be used.
        
        Args:
            threads: List of conversation threads
            emails: List of email messages
        
        Returns:
            True if hierarchical mode should be activated
        """
        if not self.config.enable:
            return False
        
        return (len(threads) >= self.config.min_threads or 
                len(emails) >= self.config.min_emails)
    
    def process_hierarchical(
        self, 
        threads: List[ConversationThread],
        all_chunks: List[EvidenceChunk],
        digest_date: str,
        trace_id: str
    ) -> EnhancedDigest:
        """
        Process threads hierarchically.
        
        Args:
            threads: List of conversation threads
            all_chunks: All evidence chunks
            digest_date: Date for the digest
            trace_id: Trace ID for logging
        
        Returns:
            EnhancedDigest v2 instance
        """
        start_time = time.time()
        
        logger.info("Starting hierarchical processing",
                   threads=len(threads),
                   chunks=len(all_chunks),
                   hierarchical_mode=True,
                   trace_id=trace_id)
        
        # Step 1: Group chunks by thread
        thread_chunks = self._group_chunks_by_thread(threads, all_chunks)
        
        # Step 2: Filter threads for summarization (skip small threads)
        threads_to_summarize = self._filter_threads_for_summarization(thread_chunks)
        
        # Step 3: Parallel per-thread summarization
        parallel_start = time.time()
        thread_summaries = self._summarize_threads_parallel(threads_to_summarize, trace_id)
        self.metrics.parallel_time_ms = int((time.time() - parallel_start) * 1000)
        
        # Step 4: Prepare final aggregator input (thread summaries + small thread chunks)
        aggregator_input = self._prepare_aggregator_input(
            thread_summaries, 
            thread_chunks,
            threads_to_summarize
        )
        
        # Step 5: Final aggregation to EnhancedDigest v2
        digest = self._final_aggregation(aggregator_input, digest_date, trace_id)
        
        # Update metrics
        self.metrics.total_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info("Hierarchical processing completed",
                   trace_id=trace_id,
                   **self.metrics.to_dict())
        
        return digest
    
    def _group_chunks_by_thread(
        self, 
        threads: List[ConversationThread],
        all_chunks: List[EvidenceChunk]
    ) -> Dict[str, List[EvidenceChunk]]:
        """
        Group evidence chunks by thread/conversation ID.
        
        Args:
            threads: List of conversation threads
            all_chunks: All evidence chunks
        
        Returns:
            Dict mapping conversation_id to list of chunks
        """
        thread_chunks = defaultdict(list)
        
        for chunk in all_chunks:
            conv_id = chunk.conversation_id
            thread_chunks[conv_id].append(chunk)
        
        # Sort chunks by priority score within each thread
        for conv_id in thread_chunks:
            thread_chunks[conv_id].sort(key=lambda c: c.priority_score, reverse=True)
        
        logger.info("Grouped chunks by thread",
                   threads=len(thread_chunks),
                   avg_chunks_per_thread=sum(len(c) for c in thread_chunks.values()) / len(thread_chunks) if thread_chunks else 0)
        
        return dict(thread_chunks)
    
    def _filter_threads_for_summarization(self, thread_chunks: Dict) -> Dict:
        """
        Skip threads with < 3 chunks (dynamic filtering).
        
        Args:
            thread_chunks: Dict mapping thread_id to chunks
        
        Returns:
            Filtered dict with only threads >= 3 chunks
        """
        filtered = {}
        skipped = 0
        
        for thread_id, chunks in thread_chunks.items():
            if len(chunks) >= 3:
                # Take up to per_thread_max_chunks_in
                filtered[thread_id] = chunks[:self.config.per_thread_max_chunks_in]
            else:
                # Skip thread_summarize, chunks go directly to aggregator
                skipped += 1
        
        self.metrics.threads_skipped_small = skipped
        
        logger.info("Filtered threads for summarization",
                   total=len(thread_chunks),
                   to_summarize=len(filtered),
                   skipped_small=skipped)
        
        return filtered
    
    def _summarize_threads_parallel(
        self, 
        threads_to_summarize: Dict,
        trace_id: str
    ) -> List[ThreadSummary]:
        """
        Parallel per-thread summarization with timeout and degradation.
        
        Args:
            threads_to_summarize: Dict mapping thread_id to chunks
            trace_id: Trace ID for logging
        
        Returns:
            List of ThreadSummary objects
        """
        summaries = []
        
        if not threads_to_summarize:
            logger.info("No threads to summarize")
            return summaries
        
        logger.info("Starting parallel thread summarization",
                   threads=len(threads_to_summarize),
                   pool_size=self.config.parallel_pool)
        
        with ThreadPoolExecutor(max_workers=self.config.parallel_pool) as executor:
            futures = {}
            
            for thread_id, chunks in threads_to_summarize.items():
                future = executor.submit(
                    self._summarize_single_thread, 
                    thread_id, 
                    chunks,
                    trace_id
                )
                futures[future] = (thread_id, chunks)
            
            for future in as_completed(futures):
                thread_id, chunks = futures[future]
                try:
                    summary = future.result(timeout=self.config.timeout_sec)
                    summaries.append(summary)
                    self.metrics.threads_summarized += 1
                    
                except FuturesTimeoutError:
                    logger.warning("Thread summarization timeout, degrading",
                                 thread_id=thread_id,
                                 timeout_sec=self.config.timeout_sec)
                    self.metrics.timeouts += 1
                    
                    # Degrade: create minimal summary from best 2 chunks
                    degraded = self._degrade_thread_summary(thread_id, chunks[:2])
                    summaries.append(degraded)
                    
                except Exception as e:
                    logger.error("Thread summarization failed",
                               thread_id=thread_id, 
                               error=str(e))
                    self.metrics.errors += 1
                    
                    # Try to create minimal summary anyway
                    try:
                        degraded = self._degrade_thread_summary(thread_id, chunks[:2])
                        summaries.append(degraded)
                    except Exception:
                        pass  # Skip this thread if degradation also fails
        
        logger.info("Parallel thread summarization completed",
                   summaries=len(summaries),
                   timeouts=self.metrics.timeouts,
                   errors=self.metrics.errors)
        
        return summaries
    
    def _summarize_single_thread(
        self, 
        thread_id: str, 
        chunks: List[EvidenceChunk],
        trace_id: str
    ) -> ThreadSummary:
        """
        Summarize single thread using LLM.
        
        Args:
            thread_id: Thread/conversation ID
            chunks: Evidence chunks for this thread
            trace_id: Trace ID for logging
        
        Returns:
            ThreadSummary object
        """
        # Prepare chunks text
        chunks_text = self._prepare_thread_chunks_text(chunks)
        
        # Load prompt
        try:
            env = Environment(loader=FileSystemLoader(Path("prompts")))
            template = env.get_template("thread_summarize.v1.j2")
        except Exception:
            # Try relative to digest-core directory
            env = Environment(loader=FileSystemLoader(Path("digest-core/prompts")))
            template = env.get_template("thread_summarize.v1.j2")
        
        rendered = template.render(
            thread_id=thread_id,
            chunk_count=len(chunks),
            chunks=chunks_text
        )
        
        # Call LLM
        messages = [{"role": "user", "content": rendered}]
        response = self.llm_gateway._make_request_with_retry(messages, f"{trace_id}_thread_{thread_id}")
        
        # Parse and validate
        response_data = response.get("data", {})
        
        # Check if data is already a dict (parsed by gateway)
        if isinstance(response_data, dict):
            parsed = response_data
        else:
            # Parse string response (fallback for older gateway versions)
            # Try to parse JSON (may have markdown code blocks)
            if "```json" in response_data:
                # Extract JSON from code block
                json_start = response_data.find("```json") + 7
                json_end = response_data.find("```", json_start)
                json_str = response_data[json_start:json_end].strip()
            elif response_data.strip().startswith("{"):
                json_str = response_data.strip()
            else:
                # Try to find first {
                json_start = response_data.find("{")
                if json_start != -1:
                    json_str = response_data[json_start:]
                else:
                    raise ValueError("No JSON found in response")
            
            parsed = json.loads(json_str)
        
        # Apply smart truncation before validation
        parsed = self._smart_truncate_parsed(parsed)

        summary = ThreadSummary(**parsed)

        # Track tokens
        self.metrics.per_thread_tokens.append(len(chunks_text.split()) * 1.3)

        return summary

    def _smart_truncate_parsed(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply smart truncation to parsed data before validation.

        Args:
            parsed: Raw parsed data from LLM

        Returns:
            Truncated data that should pass validation
        """
        # Truncate summary to 600 chars max
        if parsed.get("summary") and len(parsed["summary"]) > 600:
            summary = parsed["summary"]
            # Try to truncate at sentence boundary
            truncated = self._truncate_at_sentence_boundary(summary, 600)
            parsed["summary"] = truncated
            logger.info("Truncated summary", original_length=len(summary), truncated_length=len(truncated))

        # Truncate quotes in pending_actions
        if parsed.get("pending_actions"):
            for action in parsed["pending_actions"]:
                if action.get("quote") and len(action["quote"]) > 300:
                    quote = action["quote"]
                    truncated_quote = self._truncate_at_sentence_boundary(quote, 300)
                    action["quote"] = truncated_quote
                    logger.info("Truncated action quote", original_length=len(quote), truncated_length=len(truncated_quote))

        # Truncate quotes in deadlines
        if parsed.get("deadlines"):
            for deadline in parsed["deadlines"]:
                if deadline.get("quote") and len(deadline["quote"]) > 300:
                    quote = deadline["quote"]
                    truncated_quote = self._truncate_at_sentence_boundary(quote, 300)
                    deadline["quote"] = truncated_quote
                    logger.info("Truncated deadline quote", original_length=len(quote), truncated_length=len(truncated_quote))

        return parsed

    def _truncate_at_sentence_boundary(self, text: str, max_length: int) -> str:
        """
        Truncate text at sentence boundary, keeping under max_length.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text ending at sentence boundary
        """
        import re

        if len(text) <= max_length:
            return text

        # Try to truncate at sentence end (. ! ?)
        sentence_endings = ['.', '!', '?']
        for ending in sentence_endings:
            # Find last occurrence of sentence ending within limit
            pattern = r'.*?\\' + re.escape(ending) + r'\s*'
            match = re.search(pattern, text[:max_length + 50])  # Look a bit ahead
            if match:
                truncated = match.group(0).strip()
                if len(truncated) <= max_length:
                    return truncated + "..."

        # If no sentence boundary found, truncate at word boundary
        words = text[:max_length].split()
        if len(words) > 1:
            return " ".join(words[:-1]) + "..."

        # Last resort: hard truncate
        return text[:max_length - 3] + "..."

    def _prepare_thread_chunks_text(self, chunks: List[EvidenceChunk]) -> str:
        """
        Prepare chunks text for thread summarization.
        
        Args:
            chunks: Evidence chunks
        
        Returns:
            Formatted chunks text
        """
        parts = []
        
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"Chunk {i} (Evidence ID: {chunk.evidence_id}):")
            parts.append(chunk.content)
            parts.append("")
        
        return "\n".join(parts)
    
    def _degrade_thread_summary(
        self, 
        thread_id: str, 
        chunks: List[EvidenceChunk]
    ) -> ThreadSummary:
        """
        Create degraded thread summary from best chunks (fallback on timeout/error).
        
        Args:
            thread_id: Thread/conversation ID
            chunks: Top chunks (usually 2)
        
        Returns:
            Minimal ThreadSummary
        """
        # Create minimal summary from chunk contents
        summary_text = "Thread summary (degraded): " + " | ".join(
            c.content[:100] for c in chunks
        )[:300]
        
        evidence_ids = [c.evidence_id for c in chunks]
        
        return ThreadSummary(
            thread_id=thread_id,
            summary=summary_text,
            pending_actions=[],
            deadlines=[],
            who_must_act=[],
            open_questions=[],
            evidence_ids=evidence_ids
        )
    
    def _prepare_aggregator_input(
        self,
        thread_summaries: List[ThreadSummary],
        all_thread_chunks: Dict,
        summarized_threads: Dict
    ) -> str:
        """
        Prepare final aggregator input.
        
        Combines:
        - Thread summaries (for large threads)
        - Direct chunks (for small threads < 3 chunks)
        - Thread headers (From/Subject/Recency)
        
        Args:
            thread_summaries: List of thread summaries
            all_thread_chunks: All thread chunks
            summarized_threads: Threads that were summarized
        
        Returns:
            Formatted aggregator input text
        """
        parts = []
        
        # Add thread summaries (large threads)
        for summary in thread_summaries:
            parts.append(f"=== Thread: {summary.thread_id} ===")
            parts.append(f"Summary: {summary.summary}")
            
            if summary.pending_actions:
                parts.append(f"\nActions ({len(summary.pending_actions)}):")
                for action in summary.pending_actions:
                    parts.append(f"  - {action.title}")
                    parts.append(f"    Evidence: {action.evidence_id}")
                    parts.append(f"    Quote: \"{action.quote}\"")
                    parts.append(f"    Who must act: {action.who_must_act}")
            
            if summary.deadlines:
                parts.append(f"\nDeadlines ({len(summary.deadlines)}):")
                for dl in summary.deadlines:
                    parts.append(f"  - {dl.title} at {dl.date_time}")
                    parts.append(f"    Evidence: {dl.evidence_id}")
                    parts.append(f"    Quote: \"{dl.quote}\"")
            
            if summary.open_questions:
                parts.append(f"\nOpen questions:")
                for q in summary.open_questions:
                    parts.append(f"  - {q}")
            
            parts.append("")
        
        # Add direct chunks from small threads
        for thread_id, chunks in all_thread_chunks.items():
            if thread_id not in summarized_threads and len(chunks) < 3:
                parts.append(f"=== Thread: {thread_id} (direct chunks) ===")
                for chunk in chunks:
                    parts.append(f"Evidence {chunk.evidence_id}:")
                    parts.append(chunk.content[:300])  # Truncate for token budget
                parts.append("")
        
        input_text = "\n".join(parts)
        
        # Apply token cap with shrink logic
        estimated_tokens = int(len(input_text.split()) * 1.3)
        if estimated_tokens > self.config.final_input_token_cap:
            logger.info("Aggregator input exceeds token cap, applying shrink",
                       estimated_tokens=estimated_tokens,
                       cap=self.config.final_input_token_cap)
            input_text = self._shrink_aggregator_input(input_text, thread_summaries)
        
        self.metrics.final_input_tokens = int(len(input_text.split()) * 1.3)
        
        logger.info("Prepared aggregator input",
                   estimated_tokens=self.metrics.final_input_tokens,
                   thread_summaries=len(thread_summaries))
        
        return input_text
    
    def _shrink_aggregator_input(
        self, 
        input_text: str, 
        summaries: List[ThreadSummary]
    ) -> str:
        """
        Shrink aggregator input to fit token cap.
        
        Priority: keep threads with deadlines/actions, cut others.
        
        Args:
            input_text: Current input text
            summaries: Thread summaries
        
        Returns:
            Shrunk input text
        """
        # Prioritize summaries with actions/deadlines
        priority_summaries = []
        other_summaries = []
        
        for summary in summaries:
            if summary.pending_actions or summary.deadlines:
                priority_summaries.append(summary)
            else:
                other_summaries.append(summary)
        
        # Rebuild input with priority summaries first
        parts = []
        for summary in priority_summaries:
            parts.append(f"=== Thread: {summary.thread_id} ===")
            parts.append(f"Summary: {summary.summary}")
            
            if summary.pending_actions:
                parts.append(f"\nActions ({len(summary.pending_actions)}):")
                for action in summary.pending_actions[:3]:  # Limit to top 3
                    parts.append(f"  - {action.title} (ev: {action.evidence_id})")
            
            if summary.deadlines:
                parts.append(f"\nDeadlines ({len(summary.deadlines)}):")
                for dl in summary.deadlines[:3]:  # Limit to top 3
                    parts.append(f"  - {dl.title} at {dl.date_time} (ev: {dl.evidence_id})")
            
            parts.append("")
        
        # Add other summaries if space permits
        current_text = "\n".join(parts)
        current_tokens = int(len(current_text.split()) * 1.3)
        
        for summary in other_summaries:
            summary_text = f"=== Thread: {summary.thread_id} ===\nSummary: {summary.summary}\n\n"
            summary_tokens = int(len(summary_text.split()) * 1.3)
            
            if current_tokens + summary_tokens <= self.config.final_input_token_cap:
                parts.append(summary_text)
                current_tokens += summary_tokens
            else:
                break
        
        return "\n".join(parts)
    
    def _final_aggregation(
        self,
        aggregator_input: str,
        digest_date: str,
        trace_id: str
    ) -> EnhancedDigest:
        """
        Final aggregation to EnhancedDigest v2.
        
        Args:
            aggregator_input: Prepared input text with thread summaries
            digest_date: Date for the digest
            trace_id: Trace ID for logging
        
        Returns:
            EnhancedDigest v2 instance
        """
        logger.info("Starting final aggregation",
                   trace_id=trace_id,
                   input_tokens=self.metrics.final_input_tokens)
        
        # Use existing process_digest with v2 prompt
        # Input is now thread summaries instead of raw chunks
        result = self.llm_gateway.process_digest(
            evidence=[],  # Empty, we use custom input
            digest_date=digest_date,
            trace_id=trace_id,
            prompt_version="v2",
            custom_input=aggregator_input  # Pass thread summaries
        )
        
        logger.info("Final aggregation completed",
                   trace_id=trace_id,
                   my_actions=len(result["digest"].my_actions),
                   others_actions=len(result["digest"].others_actions),
                   deadlines=len(result["digest"].deadlines_meetings))
        
        return result["digest"]

