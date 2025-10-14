"""
Main digest pipeline runner.
"""
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import List
import uuid

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
from digest_core.llm.schemas import Digest, EnhancedDigest
from digest_core.hierarchical import HierarchicalProcessor


logger = structlog.get_logger()


def run_digest(from_date: str, sources: List[str], out: str, model: str, window: str, state: str | None) -> None:
    """
    Run the complete digest pipeline.
    
    Args:
        from_date: Date to process (YYYY-MM-DD or "today")
        sources: List of source types to process (e.g., ["ews"])
        out: Output directory path
        model: LLM model identifier
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
            return
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
        ingest = EWSIngest(config.ews)
        messages = ingest.fetch_messages(digest_date, config.time)
        logger.info("Email ingestion completed", emails_fetched=len(messages))
        metrics.record_emails_total(len(messages), "fetched")
        
        # Step 2: Normalize messages
        logger.info("Starting message normalization", stage="normalize")
        normalizer = HTMLNormalizer()
        quote_cleaner = QuoteCleaner()
        
        normalized_messages = []
        for msg in messages:
            # HTML to text conversion
            text_body = normalizer.html_to_text(msg.text_body)
            
            # Truncate large bodies (200KB limit)
            text_body = normalizer.truncate_text(text_body, max_bytes=200000)
            
            # Clean quotes and signatures
            cleaned_body = quote_cleaner.clean_quotes(text_body)
            
            # Create normalized message
            normalized_msg = msg._replace(
                text_body=cleaned_body,
                subject=msg.subject
            )
            normalized_messages.append(normalized_msg)
        
        logger.info("Message normalization completed", messages_normalized=len(normalized_messages))
        
        # Step 3: Build conversation threads
        logger.info("Starting thread building", stage="threads")
        thread_builder = ThreadBuilder()
        threads = thread_builder.build_threads(normalized_messages)
        logger.info("Thread building completed", threads_created=len(threads))
        
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
                   budget_requested=selection_metrics.get('budget_requested', 0),
                   budget_applied=selection_metrics.get('budget_applied', 0),
                   shrinks_count=selection_metrics.get('shrinks_count', 0),
                   shrink_percentage=selection_metrics.get('shrink_percentage', 0),
                   **selection_metrics)
        
        # Step 6: Process with LLM
        logger.info("Starting LLM processing", stage="llm")
        llm_gateway = LLMGateway(config.llm)
        
        # NEW: Check if hierarchical mode should be used
        hierarchical_processor = HierarchicalProcessor(config.hierarchical, llm_gateway)
        use_hierarchical = hierarchical_processor.should_use_hierarchical(threads, messages)
        
        if use_hierarchical:
            logger.info("Using hierarchical mode",
                       threads=len(threads),
                       emails=len(messages),
                       trace_id=trace_id)
            
            # Hierarchical processing: per-thread summaries → final aggregation
            digest = hierarchical_processor.process_hierarchical(
                threads=threads,
                all_chunks=evidence_chunks,
                digest_date=digest_date,
                trace_id=trace_id
            )
            
            # Log hierarchical metrics
            h_metrics = hierarchical_processor.metrics.to_dict()
            logger.info("Hierarchical processing completed", **h_metrics)
            
            # Use EnhancedDigest (v2)
            digest_data = digest
            prompt_version = "v2_hierarchical"
            
        else:
            logger.info("Using flat mode (below thresholds)",
                       threads=len(threads),
                       emails=len(messages))
            
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
        
        # Step 7: Assemble outputs
        logger.info("Starting output assembly", stage="assemble")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if use_hierarchical:
            # For EnhancedDigest v2, write JSON directly and use enhanced markdown
            json_path = output_dir / f"digest-{digest_date}.json"
            json_path.write_text(
                digest_data.model_dump_json(indent=2, exclude_none=True),
                encoding='utf-8'
            )
            
            # Write Markdown output using enhanced assembler
            markdown_assembler = MarkdownAssembler()
            md_path = output_dir / f"digest-{digest_date}.md"
            markdown_assembler.write_enhanced_digest(digest_data, md_path)
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
        
        logger.info(
            "Digest run completed successfully",
            trace_id=trace_id,
            digest_date=digest_date,
            total_items=sum(len(section.items) for section in digest_data.sections)
        )
        
    except Exception as e:
        logger.error(
            "Digest run failed",
            trace_id=trace_id,
            error=str(e),
            exc_info=True
        )
        metrics.record_run_total("failed")
        raise


def run_digest_dry_run(from_date: str, sources: List[str], out: str, model: str, window: str, state: str | None) -> None:
    """
    Run digest pipeline in dry-run mode (ingest+normalize only, no LLM/assemble).
    
    Args:
        from_date: Date to process (YYYY-MM-DD or "today")
        sources: List of source types to process (e.g., ["ews"])
        out: Output directory path
        model: LLM model identifier (not used in dry-run)
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

        ingest = EWSIngest(config.ews)
        messages = ingest.fetch_messages(digest_date, config.time)
        logger.info("Email ingestion completed", emails_fetched=len(messages))
        metrics.record_emails_total(len(messages), "fetched")
        
        # Step 2: Normalize messages
        logger.info("Starting message normalization", stage="normalize")
        normalizer = HTMLNormalizer()
        quote_cleaner = QuoteCleaner()
        
        normalized_messages = []
        for msg in messages:
            # HTML to text conversion
            text_body = normalizer.html_to_text(msg.text_body)
            
            # Truncate large bodies (200KB limit)
            text_body = normalizer.truncate_text(text_body, max_bytes=200000)
            
            # Clean quotes and signatures
            cleaned_body = quote_cleaner.clean_quotes(text_body)
            
            # Create normalized message
            normalized_msg = msg._replace(
                text_body=cleaned_body,
                subject=msg.subject
            )
            normalized_messages.append(normalized_msg)
        
        logger.info("Message normalization completed", messages_normalized=len(normalized_messages))
        
        # Step 3: Build conversation threads
        logger.info("Starting thread building", stage="threads")
        thread_builder = ThreadBuilder()
        threads = thread_builder.build_threads(normalized_messages)
        logger.info("Thread building completed", threads_created=len(threads))
        
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
                   budget_requested=selection_metrics.get('budget_requested', 0),
                   budget_applied=selection_metrics.get('budget_applied', 0),
                   shrinks_count=selection_metrics.get('shrinks_count', 0),
                   shrink_percentage=selection_metrics.get('shrink_percentage', 0),
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
