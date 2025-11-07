"""Structured logging configuration with request_id propagation"""

import contextvars
import hashlib
import logging
import sys
from typing import Any, Dict, Optional
from uuid import uuid4

import structlog


# Context variable for request_id propagation
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for safe logging
    
    Args:
        api_key: The API key to hash
        
    Returns:
        Hashed API key in format "sha256:first16chars"
    """
    return f"sha256:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"


def add_request_id(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Add request_id to log entries from context variable
    
    Args:
        logger: The logger instance
        method_name: The logging method name
        event_dict: The event dictionary
        
    Returns:
        Updated event dictionary with request_id
    """
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure structured logging with structlog
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "console")
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Shared processors for all formats
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_request_id,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Format-specific processors
    if log_format == "json":
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console format for development
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set request_id in context variable
    
    Args:
        request_id: Optional request ID, generates UUID if not provided
        
    Returns:
        The request_id that was set
    """
    if request_id is None:
        request_id = f"req_{uuid4().hex[:12]}"
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """
    Get current request_id from context variable
    
    Returns:
        Current request_id or None
    """
    return request_id_var.get()


def clear_request_id() -> None:
    """Clear request_id from context variable"""
    request_id_var.set(None)
