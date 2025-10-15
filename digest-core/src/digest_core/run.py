"""
Main digest pipeline runner.
"""
import json
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import List
import uuid

# Pipeline version - bumped to 1.1.0 (breaking: removed PII)
PIPELINE_VERSION = "1.1.0"
DEFAULT_PROMPT_VERSION = "mvp.5"

from digest_core.config import Config
from digest_core.ingest.ews import EWSIngest
from digest_core.normalize.html import HTMLNormalizer
from digest_core.normalize.quotes import QuoteCleaner
from digest_core.threads.build import ThreadBuilder
from digest_core.evidence.split import EvidenceSplitter
from digest_core.select.context import ContextSelector
from digest_core.llm.gateway import LLMGateway
from digest_core.assemble.jsonout import JSONAssembler
from digest_core.assemble.markdown import MarkdownAssembler
from digest_core.observability.logs import setup_logging
from digest_core.observability.metrics import MetricsCollector
from digest_core.observability.healthz import start_health_server
from digest_core.llm.schemas import Digest, EnhancedDigest, ExtractedActionItem
from digest_core.hierarchical import HierarchicalProcessor
from digest_core.evidence.citations import CitationBuilder, CitationValidator, enrich_item_with_citations
from digest_core.evidence.actions import ActionMentionExtractor, enrich_actions_with_evidence
from digest_core.select.ranker import DigestRanker
from digest_core.llm.degrade import extractive_fallback


logger = structlog.get_logger()


def run_digest(from_date: str, sources: List[str], out: str, model: str, window: str, state: str | None, validate_citations: bool = False) -> bool:
    """
    Run the complete digest pipeline.
    
    Args:
        from_date: Date to process (YYYY-MM-DD or "today")
        sources: List of source types to process (e.g., ["ews"])
        out: Output directory path
        model: LLM model identifier
        window: Time window (calendar_day or rolling_24h)
        state: State directory path override
        validate_citations: If True, enforce citation validation
    
    Returns:
        True if citations validation passed (or not enabled), False otherwise
    """
    # Generate trace ID for this run
    trace_id = str(uuid.uuid4())
    
    # Setup logging
    setup_logging()
    
    # Load configuration
    config = Config()
    # Override model/window from CLI if provided
    if model:
        try:
            config.llm.model = model
        except Exception:
            pass
    if window in ("calendar_day", "rolling_24h"):
        try:
            config.time.window = window
        except Exception:
            pass
    
    # Initialize metrics collector
    metrics = MetricsCollector(config.observability.prometheus_port)
    
    # Start health check server
    start_health_server(port=9109, llm_config=config.llm)
    
    # Parse date
    if from_date == "today":
        digest_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        digest_date = from_date
    
    # Check for existing artifacts (idempotency with T-48h rebuild window)
    output_dir = Path(out)
    json_path = output_dir / f"digest-{digest_date}.json"
    md_path = output_dir / f"digest-{digest_date}.md"

    # Override state directory if provided (affects SyncState path)
    if state:
        try:
            state_dir = Path(state)
            state_dir.mkdir(parents=True, exist_ok=True)
            # Only change EWS sync_state_path; other components may add their own later if needed
            config.ews.sync_state_path = str(state_dir / Path(config.ews.sync_state_path).name)
        except Exception:
            pass
    
    if json_path.exists() and md_path.exists():
        # Check if artifacts are recent (within T-48h rebuild window)
        artifact_age_hours = (datetime.now(timezone.utc).timestamp() - json_path.stat().st_mtime) / 3600
        if artifact_age_hours < 48:
            logger.info("Existing artifacts found within T-48h window, skipping rebuild",
                       digest_date=digest_date,
                       artifact_age_hours=artifact_age_hours,
                       trace_id=trace_id)
            metrics.record_run_total("ok")
            return True
        else:
            logger.info("Existing artifacts outside T-48h window, rebuilding",
                       digest_date=digest_date,
                       artifact_age_hours=artifact_age_hours,
                       trace_id=trace_id)
    
    logger.info(
        "Starting digest run",
        trace_id=trace_id,
        digest_date=digest_date,
        sources=sources,
        model=model,
        output_dir=out
    )
    
    try:
        # Step 1: Ingest emails from EWS
        logger.info("Starting email ingestion", stage="ingest")
        ingest = EWSIngest(config.ews, time_config=config.time, metrics=metrics)
        messages = ingest.fetch_messages(digest_date, config.time)
        logger.info("Email ingestion completed", emails_fetched=len(messages))
        metrics.record_emails_total(len(messages), "fetched")
        
        # Step 2: Normalize messages
        logger.info("Starting message normalization", stage="normalize")
        normalizer = HTMLNormalizer()
        quote_cleaner = QuoteCleaner(
            keep_top_quote_head=config.email_cleaner.keep_top_quote_head,
            config=config.email_cleaner
        )
        
        normalized_messages = []
        total_removed_chars = 0
        total_removed_blocks = 0
        
        for msg in messages:
            # HTML to text conversion
            text_body = normalizer.html_to_text(msg.text_body)
            
            # Truncate large bodies (200KB limit)
            text_body = normalizer.truncate_text(text_body, max_bytes=200000)
            
            # Clean quotes and signatures with span tracking (new extractive pipeline)
            if config.email_cleaner.enabled:
                cleaned_body, removed_spans = quote_cleaner.clean_email_body(text_body, lang="auto", policy="standard")
                
                # Record metrics
                for span in removed_spans:
                    span_chars = span.end - span.start
                    total_removed_chars += span_chars
                    total_removed_blocks += 1
                    metrics.record_cleaner_removed_chars(span_chars, span.type)
                    metrics.record_cleaner_removed_blocks(1, span.type)
            else:
                cleaned_body = text_body
            
            # Create normalized message
            normalized_msg = msg._replace(
                text_body=cleaned_body,
                subject=msg.subject
            )
            normalized_messages.append(normalized_msg)
        
        logger.info("Message normalization completed", 
                   messages_normalized=len(normalized_messages),
                   total_removed_chars=total_removed_chars,
                   total_removed_blocks=total_removed_blocks)
        
        # Build normalized messages map for citation tracking
        normalized_messages_map = {
            msg.msg_id: msg.text_body
            for msg in normalized_messages
        }
        logger.info("Built normalized messages map", map_size=len(normalized_messages_map))
        
        # Step 3: Build conversation threads
        logger.info("Starting thread building", stage="threads")
        original_message_count = len(normalized_messages)
        thread_builder = ThreadBuilder()
        threads = thread_builder.build_threads(normalized_messages)
        
        # Record threading metrics
        thread_stats = thread_builder.get_stats()
        if thread_stats.get('threads_merged_by_id', 0) > 0:
            metrics.record_thread_merged('by_id')
        if thread_stats.get('threads_merged_by_subject', 0) > 0:
            metrics.record_thread_merged('by_subject')
        if thread_stats.get('threads_merged_by_semantic', 0) > 0:
            metrics.record_thread_merged('by_semantic')
        if thread_stats.get('subjects_normalized', 0) > 0:
            metrics.record_subject_normalized(thread_stats['subjects_normalized'])
        if thread_stats.get('duplicates_found', 0) > 0:
            metrics.record_duplicate_found(thread_stats['duplicates_found'])
        
        # Calculate redundancy index
        unique_message_count = sum(len(t.messages) for t in threads)
        redundancy = thread_builder.calculate_redundancy_index(original_message_count, unique_message_count)
        metrics.update_redundancy_index(redundancy)
        
        logger.info("Thread building completed",
                   threads_created=len(threads),
                   redundancy_reduction=f"{redundancy*100:.1f}%",
                   **thread_stats)
        
        # Step 4: Split into evidence chunks
        logger.info("Starting evidence splitting", stage="evidence")
        evidence_splitter = EvidenceSplitter(
            user_aliases=config.ews.user_aliases,
            user_timezone=config.time.user_timezone,
            context_budget_config=config.context_budget,
            chunking_config=config.chunking
        )
        # Pass statistics for adaptive chunking
        total_emails = len(messages)
        total_threads = len(threads)
        evidence_chunks = evidence_splitter.split_evidence(threads, total_emails, total_threads)
        logger.info("Evidence splitting completed", 
                   evidence_chunks=len(evidence_chunks),
                   total_emails=total_emails,
                   total_threads=total_threads)
        
        # Step 4.5: Extract actions and mentions (rule-based)
        logger.info("Starting action/mention extraction", stage="actions")
        action_extractor = ActionMentionExtractor(
            user_aliases=config.ews.user_aliases,
            user_timezone=config.time.user_timezone
        )
        
        all_extracted_actions = []
        for msg in normalized_messages:
            # Extract actions from this message
            msg_actions = action_extractor.extract_mentions_actions(
                text=msg.text_body,
                msg_id=msg.msg_id,
                sender=msg.sender,
                sender_rank=0.5  # TODO: implement sender ranking
            )
            
            # Enrich with evidence_id
            msg_actions = enrich_actions_with_evidence(msg_actions, evidence_chunks, msg.msg_id)
            
            # Record metrics
            for action in msg_actions:
                metrics.record_action_found(action.type)
                metrics.record_action_confidence(action.confidence)
                if action.type == "mention":
                    metrics.record_mention_found()
            
            all_extracted_actions.extend(msg_actions)
        
        logger.info("Action/mention extraction completed",
                   total_actions=len(all_extracted_actions),
                   avg_confidence=sum(a.confidence for a in all_extracted_actions) / len(all_extracted_actions) if all_extracted_actions else 0)
        
        # Step 5: Select relevant context
        logger.info("Starting context selection", stage="select")
        context_selector = ContextSelector(
            buckets_config=config.selection_buckets,
            weights_config=config.selection_weights,
            context_budget_config=config.context_budget,
            shrink_config=config.shrink
        )
        selected_evidence = context_selector.select_context(evidence_chunks)
        selection_metrics = context_selector.get_metrics()
        logger.info("Context selection completed", 
                   evidence_selected=len(selected_evidence),
                   **selection_metrics)
        
        # Shortcut: Skip LLM if no evidence selected
        if len(selected_evidence) == 0:
            logger.warning("No evidence selected, skipping LLM and using extractive fallback",
                          trace_id=trace_id,
                          reason="no_evidence")
            
            # Use extractive fallback with all chunks (not just selected)
            digest_data = extractive_fallback(
                evidence_chunks=evidence_chunks,
                digest_date=digest_date,
                trace_id=trace_id,
                reason="no_evidence"
            )
            
            # Mark as partial
            output_dir = Path(out)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Write JSON with partial flag
            json_path = output_dir / f"digest-{digest_date}.json"
            digest_dict = digest_data.model_dump(exclude_none=True)
            digest_dict['partial'] = True
            digest_dict['reason'] = 'no_evidence'
            json_path.write_text(
                json.dumps(digest_dict, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            
            # Write Markdown
            markdown_assembler = MarkdownAssembler()
            md_path = output_dir / f"digest-{digest_date}.md"
            markdown_assembler.write_enhanced_digest(digest_data, md_path)
            
            logger.info("Output assembly completed (no evidence fallback)", 
                       json_path=str(json_path), 
                       md_path=str(md_path))
            
            metrics.record_run_total("ok")
            metrics.record_digest_build_time()
            
            logger.info(
                "Digest run completed with no evidence shortcut",
                trace_id=trace_id,
                digest_date=digest_date,
                total_items=0
            )
            return
        
        # Step 6: Process with LLM
        logger.info("Starting LLM processing", stage="llm")
        llm_gateway = LLMGateway(config.llm, metrics=metrics)
        
        # NEW: Check if hierarchical mode should be used
        hierarchical_processor = HierarchicalProcessor(config.hierarchical, llm_gateway)
        use_hierarchical = hierarchical_processor.should_use_hierarchical(threads, messages)
        
        # Initialize partial flags
        is_partial = False
        partial_reason = None
        
        if use_hierarchical:
            # Determine trigger reason for metrics
            trigger_reason = "manual"
            if config.hierarchical.auto_enable:
                if len(threads) >= config.hierarchical.min_threads:
                    trigger_reason = "auto_threads"
                elif len(messages) >= config.hierarchical.min_emails:
                    trigger_reason = "auto_emails"
            
            metrics.record_hierarchical_run(trigger_reason)
            
            logger.info("Using hierarchical mode",
                       threads=len(threads),
                       emails=len(messages),
                       trigger_reason=trigger_reason,
                       trace_id=trace_id)
            
            try:
                # Hierarchical processing: per-thread summaries → final aggregation
                digest = hierarchical_processor.process_hierarchical(
                    threads=threads,
                    all_chunks=evidence_chunks,
                    digest_date=digest_date,
                    trace_id=trace_id,
                    user_aliases=config.ews.user_aliases
                )
                
                # Log hierarchical metrics
                h_metrics = hierarchical_processor.metrics.to_dict()
                logger.info("Hierarchical processing completed", **h_metrics)
                
                # Calculate and record avg subsummary chunks
                if h_metrics.get('threads_summarized', 0) > 0:
                    avg_chunks = sum(hierarchical_processor.metrics.per_thread_tokens) / h_metrics['threads_summarized']
                    # Rough estimate: tokens to chunks
                    avg_chunks_estimate = avg_chunks / 300  # Assume ~300 tokens per chunk
                    metrics.update_avg_subsummary_chunks(avg_chunks_estimate)
                
                # Use EnhancedDigest (v2)
                digest_data = digest
                prompt_version = "v2_hierarchical"
                
            except Exception as hierarchical_err:
                logger.error("Hierarchical processing failed, using fallback",
                           error=str(hierarchical_err),
                           trace_id=trace_id)
                
                # Determine reason for degradation
                reason = "llm_json_error" if "JSON" in str(hierarchical_err) else "llm_processing_failed"
                
                # Record degradation metric
                metrics.record_degradation(reason)
                
                # Use extractive fallback
                digest_data = extractive_fallback(
                    evidence_chunks=evidence_chunks,
                    digest_date=digest_date,
                    trace_id=trace_id,
                    reason=reason
                )
                
                prompt_version = "extractive_fallback"
                is_partial = True
                partial_reason = reason
            
            # Enrich items with email subjects and collect statistics
            evidence_to_subject = {chunk.evidence_id: chunk.message_metadata.get("subject", "") 
                                  for chunk in evidence_chunks}
            unique_msg_ids = set()
            
            # Enrich all action types
            for action in digest_data.my_actions + digest_data.others_actions:
                action.email_subject = evidence_to_subject.get(action.evidence_id, "")
                # Track msg_ids by looking up the chunk
                for chunk in evidence_chunks:
                    if chunk.evidence_id == action.evidence_id:
                        if chunk.source_ref.get("msg_id"):
                            unique_msg_ids.add(chunk.source_ref["msg_id"])
                        break
            
            for item in digest_data.deadlines_meetings:
                item.email_subject = evidence_to_subject.get(item.evidence_id, "")
                for chunk in evidence_chunks:
                    if chunk.evidence_id == item.evidence_id:
                        if chunk.source_ref.get("msg_id"):
                            unique_msg_ids.add(chunk.source_ref["msg_id"])
                        break
            
            for item in digest_data.risks_blockers:
                item.email_subject = evidence_to_subject.get(item.evidence_id, "")
                for chunk in evidence_chunks:
                    if chunk.evidence_id == item.evidence_id:
                        if chunk.source_ref.get("msg_id"):
                            unique_msg_ids.add(chunk.source_ref["msg_id"])
                        break
            
            for item in digest_data.fyi:
                item.email_subject = evidence_to_subject.get(item.evidence_id, "")
                for chunk in evidence_chunks:
                    if chunk.evidence_id == item.evidence_id:
                        if chunk.source_ref.get("msg_id"):
                            unique_msg_ids.add(chunk.source_ref["msg_id"])
                        break
            
            # Add statistics
            digest_data.total_emails_processed = len(messages)
            digest_data.emails_with_actions = len(unique_msg_ids)
            
        else:
            logger.info("Using flat mode (below thresholds)",
                       threads=len(threads),
                       emails=len(messages))
            
            try:
                # Load prompts (switch to EN prompt for qwen models)
                prompts_dir = Path("prompts")
                model_lower = (config.llm.model or "").lower()
                extract_prompt_name = "extract_actions.en.v1.j2" if "qwen" in model_lower else "extract_actions.v1.j2"
                extract_prompt = (prompts_dir / extract_prompt_name).read_text()
                prompt_version = "extract_actions.en.v1" if "qwen" in model_lower else "extract_actions.v1"
                
                # Send to LLM and validate response
                llm_response = llm_gateway.extract_actions(
                    evidence=selected_evidence,
                    prompt_template=extract_prompt,
                    trace_id=trace_id
                )
                
                # Validate response against schema
                digest_data = Digest(
                    schema_version="1.0",
                    prompt_version=prompt_version,
                    digest_date=digest_date,
                    trace_id=trace_id,
                    sections=llm_response.get("sections", [])
                )
                
            except Exception as flat_err:
                logger.error("Flat mode LLM processing failed, using fallback",
                           error=str(flat_err),
                           trace_id=trace_id)
                
                # Determine reason for degradation
                reason = "llm_json_error" if "JSON" in str(flat_err) else "llm_processing_failed"
                
                # Record degradation metric
                metrics.record_degradation(reason)
                
                # Use extractive fallback - convert to EnhancedDigest
                digest_data = extractive_fallback(
                    evidence_chunks=evidence_chunks,
                    digest_date=digest_date,
                    trace_id=trace_id,
                    reason=reason
                )
                
                prompt_version = "extractive_fallback"
                is_partial = True
                partial_reason = reason
            
            # Enrich items with email subjects and collect statistics
            evidence_to_subject = {chunk.evidence_id: chunk.message_metadata.get("subject", "") 
                                  for chunk in evidence_chunks}
            unique_msg_ids = set()
            
            # Check if digest_data is Digest (v1) or EnhancedDigest (fallback)
            if isinstance(digest_data, Digest):
                for section in digest_data.sections:
                    for item in section.items:
                        # Add email subject
                        item.email_subject = evidence_to_subject.get(item.evidence_id, "")
                        # Track unique msg_ids for statistics
                        if item.source_ref.get("msg_id"):
                            unique_msg_ids.add(item.source_ref["msg_id"])
                
                # Add statistics
                digest_data.total_emails_processed = len(messages)
                digest_data.emails_with_actions = len(unique_msg_ids)
            else:
                # EnhancedDigest - enrich all action types
                for action in digest_data.my_actions + digest_data.others_actions:
                    action.email_subject = evidence_to_subject.get(action.evidence_id, "")
                    for chunk in evidence_chunks:
                        if chunk.evidence_id == action.evidence_id:
                            if chunk.source_ref.get("msg_id"):
                                unique_msg_ids.add(chunk.source_ref["msg_id"])
                            break
                
                for item in digest_data.deadlines_meetings + digest_data.risks_blockers + digest_data.fyi:
                    item.email_subject = evidence_to_subject.get(item.evidence_id, "")
                    for chunk in evidence_chunks:
                        if chunk.evidence_id == item.evidence_id:
                            if chunk.source_ref.get("msg_id"):
                                unique_msg_ids.add(chunk.source_ref["msg_id"])
                            break
                
                # Add statistics
                digest_data.total_emails_processed = len(messages)
                digest_data.emails_with_actions = len(unique_msg_ids)
        
        # Metrics for LLM
        if use_hierarchical:
            # For EnhancedDigest, count items differently
            total_items = (len(digest_data.my_actions) + len(digest_data.others_actions) + 
                          len(digest_data.deadlines_meetings) + len(digest_data.risks_blockers) + 
                          len(digest_data.fyi))
            logger.info("LLM processing completed (hierarchical)", total_items=total_items)
        else:
            logger.info("LLM processing completed", sections_count=len(digest_data.sections))
        
        metrics.record_llm_latency(llm_gateway.last_latency_ms)
        
        if not use_hierarchical:
            meta = llm_response.get("_meta", {})
            tokens_in = meta.get("tokens_in") or 0
            tokens_out = meta.get("tokens_out") or 0
            try:
                metrics.record_llm_tokens(int(tokens_in or 0), int(tokens_out or 0))
            except Exception:
                pass
        
        # Step 6.5: Enrich with citations (extractive traceability)
        logger.info("Starting citation enrichment", stage="citations")
        citation_builder = CitationBuilder(normalized_messages_map)
        citation_validation_passed = True
        
        # Enrich all digest items with citations
        all_items = []
        if use_hierarchical:
            all_items.extend(digest_data.my_actions)
            all_items.extend(digest_data.others_actions)
            all_items.extend(digest_data.deadlines_meetings)
            all_items.extend(digest_data.risks_blockers)
            all_items.extend(digest_data.fyi)
        else:
            for section in digest_data.sections:
                all_items.extend(section.items)
        
        for item in all_items:
            enrich_item_with_citations(item, evidence_chunks, citation_builder)
            # Record metric for citations per item
            metrics.record_citations_per_item(len(item.citations))
        
        logger.info("Citation enrichment completed", 
                   total_items=len(all_items),
                   total_citations=sum(len(item.citations) for item in all_items))
        
        # Validate citations if requested
        if validate_citations:
            logger.info("Starting citation validation")
            citation_validator = CitationValidator(normalized_messages_map)
            
            # Collect all citations
            all_citations = []
            for item in all_items:
                all_citations.extend(item.citations)
            
            # Run validation
            citation_validation_passed = citation_validator.validate_citations(
                all_citations, 
                strict=False  # Collect all errors, not just first
            )
            
            if not citation_validation_passed:
                logger.error("Citation validation failed",
                           errors=len(citation_validator.validation_errors),
                           error_details=citation_validator.validation_errors[:10])  # Log first 10 errors
                
                # Record validation failures
                for error_info in citation_validator.validation_errors:
                    # Extract failure type from error message
                    error_msg = error_info.get('error', '')
                    if 'offset' in error_msg.lower():
                        failure_type = 'offset_invalid'
                    elif 'checksum' in error_msg.lower():
                        failure_type = 'checksum_mismatch'
                    elif 'not found' in error_msg.lower():
                        failure_type = 'not_found'
                    elif 'preview mismatch' in error_msg.lower():
                        failure_type = 'preview_mismatch'
                    else:
                        failure_type = 'other'
                    
                    metrics.record_citation_validation_failure(failure_type)
            else:
                logger.info("Citation validation passed", total_citations=len(all_citations))
        
        # Step 6.6: Enrich extracted actions with citations and add to digest
        if use_hierarchical and all_extracted_actions:
            logger.info("Enriching extracted actions with citations")
            
            # Convert ExtractedAction to ExtractedActionItem
            evidence_to_subject = {chunk.evidence_id: chunk.message_metadata.get("subject", "") 
                                  for chunk in evidence_chunks}
            
            for action in all_extracted_actions:
                # Create ExtractedActionItem
                extracted_item = ExtractedActionItem(
                    type=action.type,
                    who=action.who,
                    verb=action.verb,
                    text=action.text,
                    due=action.due,
                    confidence=action.confidence,
                    evidence_id=action.evidence_id,
                    email_subject=evidence_to_subject.get(action.evidence_id, "")
                )
                
                # Enrich with citations
                enrich_item_with_citations(extracted_item, evidence_chunks, citation_builder)
                metrics.record_citations_per_item(len(extracted_item.citations))
                
                # Add to digest
                digest_data.extracted_actions.append(extracted_item)
            
            # Sort by confidence (highest first)
            digest_data.extracted_actions.sort(key=lambda a: a.confidence, reverse=True)
            
            logger.info("Extracted actions enriched and added to digest",
                       total_extracted_actions=len(digest_data.extracted_actions))
        
        # Step 6.7: Rank digest items by actionability
        if config.ranker.enabled:
            logger.info("Starting item ranking", stage="ranking")
            
            # Prepare weights from config
            weights = {
                'user_in_to': config.ranker.weight_user_in_to,
                'user_in_cc': config.ranker.weight_user_in_cc,
                'has_action': config.ranker.weight_has_action,
                'has_mention': config.ranker.weight_has_mention,
                'has_due_date': config.ranker.weight_has_due_date,
                'sender_importance': config.ranker.weight_sender_importance,
                'thread_length': config.ranker.weight_thread_length,
                'recency': config.ranker.weight_recency,
                'has_attachments': config.ranker.weight_has_attachments,
                'has_project_tag': config.ranker.weight_has_project_tag,
            }
            
            # Initialize ranker
            ranker = DigestRanker(
                weights=weights,
                user_aliases=config.ews.user_aliases,
                important_senders=config.ranker.important_senders
            )
            
            # Rank different item types
            if use_hierarchical:
                # Rank my_actions (most important)
                if digest_data.my_actions:
                    digest_data.my_actions = ranker.rank_items(digest_data.my_actions, evidence_chunks)
                    for item in digest_data.my_actions:
                        if hasattr(item, 'rank_score'):
                            metrics.record_rank_score(item.rank_score)
                
                # Rank others_actions
                if digest_data.others_actions:
                    digest_data.others_actions = ranker.rank_items(digest_data.others_actions, evidence_chunks)
                    for item in digest_data.others_actions:
                        if hasattr(item, 'rank_score'):
                            metrics.record_rank_score(item.rank_score)
                
                # Rank deadlines_meetings
                if digest_data.deadlines_meetings:
                    digest_data.deadlines_meetings = ranker.rank_items(digest_data.deadlines_meetings, evidence_chunks)
                    for item in digest_data.deadlines_meetings:
                        if hasattr(item, 'rank_score'):
                            metrics.record_rank_score(item.rank_score)
                
                # Rank risks_blockers
                if digest_data.risks_blockers:
                    digest_data.risks_blockers = ranker.rank_items(digest_data.risks_blockers, evidence_chunks)
                
                # Rank FYI
                if digest_data.fyi:
                    digest_data.fyi = ranker.rank_items(digest_data.fyi, evidence_chunks)
                
                # Calculate top10 actions share (from my_actions)
                if digest_data.my_actions:
                    top10_share = ranker.get_top_n_actions_share(digest_data.my_actions, n=min(10, len(digest_data.my_actions)))
                    metrics.update_top10_actions_share(top10_share)
            else:
                # Legacy v1: rank items within each section
                for section in digest_data.sections:
                    if section.items:
                        section.items = ranker.rank_items(section.items, evidence_chunks)
                        for item in section.items:
                            if hasattr(item, 'rank_score'):
                                metrics.record_rank_score(item.rank_score)
            
            metrics.set_ranking_enabled(True)
            logger.info("Item ranking completed")
        else:
            metrics.set_ranking_enabled(False)
            logger.info("Item ranking disabled")
        
        # Step 7: Assemble outputs
        logger.info("Starting output assembly", stage="assemble")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if use_hierarchical:
            # For EnhancedDigest v2, write JSON directly and use enhanced markdown
            json_path = output_dir / f"digest-{digest_date}.json"
            digest_dict = digest_data.model_dump(exclude_none=True)
            
            # Add partial flag and reason if present
            if is_partial:
                digest_dict['partial'] = True
                digest_dict['partial_reason'] = partial_reason
            
            json_path.write_text(
                json.dumps(digest_dict, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            
            # Write Markdown output using enhanced assembler
            markdown_assembler = MarkdownAssembler()
            md_path = output_dir / f"digest-{digest_date}.md"
            markdown_assembler.write_enhanced_digest(digest_data, md_path, is_partial=is_partial, partial_reason=partial_reason)
        else:
            # Check if digest_data is EnhancedDigest (fallback) or Digest (normal)
            if isinstance(digest_data, EnhancedDigest):
                # Fallback case - write as enhanced digest
                json_path = output_dir / f"digest-{digest_date}.json"
                digest_dict = digest_data.model_dump(exclude_none=True)
                
                # Add partial flag and reason if present
                if is_partial:
                    digest_dict['partial'] = True
                    digest_dict['partial_reason'] = partial_reason
                
                json_path.write_text(
                    json.dumps(digest_dict, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )
                
                # Write Markdown output using enhanced assembler
                markdown_assembler = MarkdownAssembler()
                md_path = output_dir / f"digest-{digest_date}.md"
                markdown_assembler.write_enhanced_digest(digest_data, md_path, is_partial=is_partial, partial_reason=partial_reason)
            else:
                # Legacy v1 output
                json_assembler = JSONAssembler()
                json_assembler.write_digest(digest_data, json_path)
                
                # Write Markdown output
                markdown_assembler = MarkdownAssembler()
                md_path = output_dir / f"digest-{digest_date}.md"
                markdown_assembler.write_digest(digest_data, md_path)
        
        logger.info("Output assembly completed", json_path=str(json_path), md_path=str(md_path))
        
        # Record success metrics
        metrics.record_run_total("ok")
        metrics.record_digest_build_time()
        
        # Calculate total items for logging
        if use_hierarchical:
            total_items = (len(digest_data.my_actions) + len(digest_data.others_actions) + 
                          len(digest_data.deadlines_meetings) + len(digest_data.risks_blockers) + 
                          len(digest_data.fyi))
        else:
            total_items = sum(len(section.items) for section in digest_data.sections)
        
        logger.info(
            "Digest run completed successfully",
            trace_id=trace_id,
            digest_date=digest_date,
            total_items=total_items,
            citations_validated=validate_citations,
            validation_passed=citation_validation_passed if validate_citations else None
        )
        
        return citation_validation_passed
        
    except Exception as e:
        logger.error(
            "Digest run failed",
            trace_id=trace_id,
            error=str(e),
            exc_info=True
        )
        metrics.record_run_total("failed")
        raise


def run_digest_dry_run(from_date: str, sources: List[str], out: str, model: str, window: str, state: str | None, validate_citations: bool = False) -> None:
    """
    Run digest pipeline in dry-run mode (ingest+normalize only, no LLM/assemble).
    
    Args:
        from_date: Date to process (YYYY-MM-DD or "today")
        sources: List of source types to process (e.g., ["ews"])
        out: Output directory path
        model: LLM model identifier (not used in dry-run)
        window: Time window (calendar_day or rolling_24h)
        state: State directory path override
        validate_citations: Not used in dry-run mode
    """
    # Generate trace ID for this run
    trace_id = str(uuid.uuid4())
    
    # Setup logging
    setup_logging()
    
    # Load configuration
    config = Config()
    # Override model/window from CLI if provided
    if model:
        try:
            config.llm.model = model
        except Exception:
            pass
    if window in ("calendar_day", "rolling_24h"):
        try:
            config.time.window = window
        except Exception:
            pass
    
    # Initialize metrics collector
    metrics = MetricsCollector(config.observability.prometheus_port)
    
    # Start health check server
    start_health_server(port=9109, llm_config=config.llm)
    
    # Parse date
    if from_date == "today":
        digest_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        digest_date = from_date
    
    logger.info(
        "Starting digest dry-run",
        trace_id=trace_id,
        digest_date=digest_date,
        sources=sources,
        model=model,
        output_dir=out
    )
    
    try:
        # Step 1: Ingest emails from EWS
        logger.info("Starting email ingestion", stage="ingest")
        # Override state directory if provided (affects SyncState path)
        if state:
            try:
                state_dir = Path(state)
                state_dir.mkdir(parents=True, exist_ok=True)
                config.ews.sync_state_path = str(state_dir / Path(config.ews.sync_state_path).name)
            except Exception:
                pass

        ingest = EWSIngest(config.ews, time_config=config.time, metrics=metrics)
        messages = ingest.fetch_messages(digest_date, config.time)
        logger.info("Email ingestion completed", emails_fetched=len(messages))
        metrics.record_emails_total(len(messages), "fetched")
        
        # Step 2: Normalize messages
        logger.info("Starting message normalization", stage="normalize")
        normalizer = HTMLNormalizer()
        quote_cleaner = QuoteCleaner(
            keep_top_quote_head=config.email_cleaner.keep_top_quote_head,
            config=config.email_cleaner
        )
        
        normalized_messages = []
        total_removed_chars = 0
        total_removed_blocks = 0
        
        for msg in messages:
            # HTML to text conversion
            text_body = normalizer.html_to_text(msg.text_body)
            
            # Truncate large bodies (200KB limit)
            text_body = normalizer.truncate_text(text_body, max_bytes=200000)
            
            # Clean quotes and signatures with span tracking (new extractive pipeline)
            if config.email_cleaner.enabled:
                cleaned_body, removed_spans = quote_cleaner.clean_email_body(text_body, lang="auto", policy="standard")
                
                # Record metrics
                for span in removed_spans:
                    span_chars = span.end - span.start
                    total_removed_chars += span_chars
                    total_removed_blocks += 1
                    metrics.record_cleaner_removed_chars(span_chars, span.type)
                    metrics.record_cleaner_removed_blocks(1, span.type)
            else:
                cleaned_body = text_body
            
            # Create normalized message
            normalized_msg = msg._replace(
                text_body=cleaned_body,
                subject=msg.subject
            )
            normalized_messages.append(normalized_msg)
        
        logger.info("Message normalization completed", 
                   messages_normalized=len(normalized_messages),
                   total_removed_chars=total_removed_chars,
                   total_removed_blocks=total_removed_blocks)
        
        # Step 3: Build conversation threads
        logger.info("Starting thread building", stage="threads")
        original_message_count = len(normalized_messages)
        thread_builder = ThreadBuilder()
        threads = thread_builder.build_threads(normalized_messages)
        
        # Record threading metrics
        thread_stats = thread_builder.get_stats()
        if thread_stats.get('threads_merged_by_id', 0) > 0:
            metrics.record_thread_merged('by_id')
        if thread_stats.get('threads_merged_by_subject', 0) > 0:
            metrics.record_thread_merged('by_subject')
        if thread_stats.get('threads_merged_by_semantic', 0) > 0:
            metrics.record_thread_merged('by_semantic')
        if thread_stats.get('subjects_normalized', 0) > 0:
            metrics.record_subject_normalized(thread_stats['subjects_normalized'])
        if thread_stats.get('duplicates_found', 0) > 0:
            metrics.record_duplicate_found(thread_stats['duplicates_found'])
        
        # Calculate redundancy index
        unique_message_count = sum(len(t.messages) for t in threads)
        redundancy = thread_builder.calculate_redundancy_index(original_message_count, unique_message_count)
        metrics.update_redundancy_index(redundancy)
        
        logger.info("Thread building completed",
                   threads_created=len(threads),
                   redundancy_reduction=f"{redundancy*100:.1f}%",
                   **thread_stats)
        
        # Step 4: Split into evidence chunks
        logger.info("Starting evidence splitting", stage="evidence")
        evidence_splitter = EvidenceSplitter(
            user_aliases=config.ews.user_aliases,
            user_timezone=config.time.user_timezone,
            context_budget_config=config.context_budget,
            chunking_config=config.chunking
        )
        # Pass statistics for adaptive chunking
        total_emails = len(messages)
        total_threads = len(threads)
        evidence_chunks = evidence_splitter.split_evidence(threads, total_emails, total_threads)
        logger.info("Evidence splitting completed", 
                   evidence_chunks=len(evidence_chunks),
                   total_emails=total_emails,
                   total_threads=total_threads)
        
        # Step 5: Select relevant context
        logger.info("Starting context selection", stage="select")
        context_selector = ContextSelector(
            buckets_config=config.selection_buckets,
            weights_config=config.selection_weights,
            context_budget_config=config.context_budget,
            shrink_config=config.shrink
        )
        selected_evidence = context_selector.select_context(evidence_chunks)
        selection_metrics = context_selector.get_metrics()
        logger.info("Context selection completed", 
                   evidence_selected=len(selected_evidence),
                   **selection_metrics)
        
        # Dry-run stops here - no LLM processing or assembly
        
        # Record success metrics
        metrics.record_run_total("ok")
        metrics.record_digest_build_time()
        
        logger.info(
            "Digest dry-run completed successfully",
            trace_id=trace_id,
            digest_date=digest_date,
            emails_processed=len(messages),
            threads_created=len(threads),
            evidence_chunks=len(evidence_chunks),
            selected_evidence=len(selected_evidence)
        )
        
    except Exception as e:
        logger.error(
            "Digest dry-run failed",
            trace_id=trace_id,
            error=str(e),
            exc_info=True
        )
        metrics.record_run_total("failed")
        raise


if __name__ == "__main__":
    # For testing
    run_digest("today", ["ews"], "./out", "corp/gpt-4o-mini")
