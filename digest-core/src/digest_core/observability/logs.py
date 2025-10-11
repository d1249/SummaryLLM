"""
Structured logging setup using structlog.
"""
import structlog
import logging
import sys
from typing import Any, Dict
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


def log_pipeline_stage(stage: str, **kwargs) -> None:
    """Log a pipeline stage with context."""
    logger = get_logger()
    logger.info(f"Pipeline stage: {stage}", stage=stage, **kwargs)


def log_error_with_context(error: Exception, **kwargs) -> None:
    """Log an error with context."""
    logger = get_logger()
    logger.error("Pipeline error", error=str(error), exc_info=True, **kwargs)


def log_metrics(metrics: Dict[str, Any]) -> None:
    """Log metrics data."""
    logger = get_logger()
    logger.info("Pipeline metrics", **metrics)
