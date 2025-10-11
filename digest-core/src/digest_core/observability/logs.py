"""
Structured logging setup using structlog with run_id/trace_id support.
"""
import structlog
import logging
import sys
import uuid
from typing import Any, Dict, Optional
import json


def setup_logging(log_level: str = "INFO") -> None:
    """Setup structured logging with structlog."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            _redact_sensitive_data,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _redact_sensitive_data(logger, method_name, event_dict):
    """Redact sensitive data from log entries."""
    
    # Fields to redact
    sensitive_fields = [
        'password', 'token', 'secret', 'key', 'auth',
        'email', 'phone', 'ssn', 'credit_card'
    ]
    
    # Patterns to redact
    sensitive_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card
    ]
    
    # Redact sensitive fields
    for field in sensitive_fields:
        if field in event_dict:
            event_dict[field] = "[[REDACTED]]"
    
    # Redact sensitive patterns in string values
    for key, value in event_dict.items():
        if isinstance(value, str):
            for pattern in sensitive_patterns:
                import re
                if re.search(pattern, value):
                    event_dict[key] = re.sub(pattern, "[[REDACTED]]", value)
    
    return event_dict


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger."""
    return structlog.get_logger(name)


def log_pipeline_stage(stage: str, run_id: str = None, trace_id: str = None, **kwargs) -> None:
    """Log a pipeline stage with context."""
    logger = get_logger()
    context = {"stage": stage}
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info(f"Pipeline stage: {stage}", **context, **kwargs)


def log_error_with_context(error: Exception, run_id: str = None, trace_id: str = None, **kwargs) -> None:
    """Log an error with context."""
    logger = get_logger()
    context = {"error": str(error)}
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.error("Pipeline error", **context, exc_info=True, **kwargs)


def log_metrics(metrics: Dict[str, Any], run_id: str = None, trace_id: str = None) -> None:
    """Log metrics data."""
    logger = get_logger()
    context = {}
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("Pipeline metrics", **context, **metrics)


def log_llm_request(model: str, tokens_in: int, tokens_out: int, latency_ms: int, 
                   run_id: str = None, trace_id: str = None, **kwargs) -> None:
    """Log LLM request details."""
    logger = get_logger()
    context = {
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms
    }
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("LLM request completed", **context, **kwargs)


def log_email_processing(count: int, status: str, run_id: str = None, trace_id: str = None, **kwargs) -> None:
    """Log email processing details."""
    logger = get_logger()
    context = {
        "email_count": count,
        "status": status
    }
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("Email processing completed", **context, **kwargs)


def log_evidence_processing(count: int, stage: str, run_id: str = None, trace_id: str = None, **kwargs) -> None:
    """Log evidence processing details."""
    logger = get_logger()
    context = {
        "evidence_count": count,
        "stage": stage
    }
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("Evidence processing completed", **context, **kwargs)


def log_digest_completion(sections_count: int, total_items: int, run_id: str = None, trace_id: str = None, **kwargs) -> None:
    """Log digest completion details."""
    logger = get_logger()
    context = {
        "sections_count": sections_count,
        "total_items": total_items
    }
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("Digest completed", **context, **kwargs)


def log_run_start(from_date: str, sources: list, out: str, model: str, run_id: str = None, trace_id: str = None) -> None:
    """Log run start details."""
    logger = get_logger()
    context = {
        "from_date": from_date,
        "sources": sources,
        "output_dir": out,
        "model": model
    }
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("Digest run started", **context)


def log_run_completion(status: str, duration_seconds: float, run_id: str = None, trace_id: str = None, **kwargs) -> None:
    """Log run completion details."""
    logger = get_logger()
    context = {
        "status": status,
        "duration_seconds": duration_seconds
    }
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("Digest run completed", **context, **kwargs)


def generate_run_id() -> str:
    """Generate a unique run ID."""
    return str(uuid.uuid4())


def generate_trace_id() -> str:
    """Generate a unique trace ID."""
    return str(uuid.uuid4())


def get_contextual_logger(run_id: str = None, trace_id: str = None) -> structlog.BoundLogger:
    """Get a logger with run_id and trace_id context."""
    logger = get_logger()
    
    context = {}
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    return logger.bind(**context)


def log_configuration(config_dict: Dict[str, Any], run_id: str = None, trace_id: str = None) -> None:
    """Log configuration details (with sensitive data redacted)."""
    logger = get_logger()
    
    # Redact sensitive configuration values
    redacted_config = {}
    for key, value in config_dict.items():
        if any(sensitive in key.lower() for sensitive in ['password', 'token', 'secret', 'key']):
            redacted_config[key] = "[[REDACTED]]"
        else:
            redacted_config[key] = value
    
    context = {"config": redacted_config}
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("Configuration loaded", **context)


def log_performance_metrics(metrics: Dict[str, Any], run_id: str = None, trace_id: str = None) -> None:
    """Log performance metrics."""
    logger = get_logger()
    context = {"performance_metrics": metrics}
    
    if run_id:
        context["run_id"] = run_id
    if trace_id:
        context["trace_id"] = trace_id
    
    logger.info("Performance metrics", **context)
