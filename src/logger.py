"""
Structured logging module for BigQuery Stock Quotes Extractor.

Provides JSON-formatted logging similar to existing project patterns,
but without Loki integration (deferred to future stages).

Supports request ID tracking using contextvars for distributed tracing.
"""

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable for request ID tracking
# This allows request ID to propagate through the call stack automatically
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'request_id',
    default=None
)


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-structured log messages."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.
        
        Args:
            record: Log record to format
        
        Returns:
            JSON-formatted log message
        """
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request ID from context if present
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        # Add extra fields if present
        if hasattr(record, "labels"):
            log_data["labels"] = record.labels
        
        if hasattr(record, "fields"):
            log_data["fields"] = record.fields
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


def build_logger(
    service_name: str,
    environment: str,
    level: str = "INFO",
) -> logging.Logger:
    """Build a structured logger with JSON formatting.
    
    Args:
        service_name: Name of the service (e.g., 'bq-stock-extractor')
        environment: Environment name (e.g., 'development', 'production')
        level: Logging level (default: 'INFO')
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create console handler with structured formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    # Add default labels
    logger.service_name = service_name
    logger.environment = environment
    
    return logger


def log_struct(
    logger: logging.Logger,
    level: str,
    message: str,
    labels: Optional[Dict[str, Any]] = None,
    fields: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a structured message with labels and fields.
    
    Args:
        logger: Logger instance
        level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        message: Log message
        labels: Key-value pairs for indexing/filtering (e.g., symbol, timeframe)
        fields: Additional structured data (e.g., query params, error context)
    """
    # Merge default labels
    default_labels = {
        "service": getattr(logger, "service_name", "unknown"),
        "environment": getattr(logger, "environment", "unknown"),
    }
    
    merged_labels = {**default_labels, **(labels or {})}
    
    # Get log method
    log_method = getattr(logger, level.lower())
    
    # Log with extra fields
    log_method(
        message,
        extra={
            "labels": merged_labels,
            "fields": fields or {},
        }
    )


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set request ID in context for log correlation.
    
    If no request_id is provided, a new UUID4 will be generated.
    The request ID will be automatically included in all subsequent log messages.
    
    Args:
        request_id: Request ID to set (if None, generates new UUID4)
    
    Returns:
        The request ID that was set
    
    Example:
        >>> request_id = set_request_id()
        >>> # All logs from this point will include this request_id
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """Get current request ID from context.
    
    Returns:
        Current request ID, or None if not set
    
    Example:
        >>> set_request_id("my-request-123")
        >>> get_request_id()
        'my-request-123'
    """
    return request_id_var.get()


def clear_request_id() -> None:
    """Clear request ID from context.
    
    Useful for cleanup or testing scenarios.
    """
    request_id_var.set(None)


def env_labels() -> Dict[str, str]:
    """Get environment-specific labels for logging.
    
    Returns:
        Dictionary of environment labels
    """
    import platform
    import socket
    
    return {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "python_version": platform.python_version(),
    }

