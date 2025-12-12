"""
Structured logging module for BigQuery Stock Quotes Extractor.

Provides JSON-formatted logging similar to existing project patterns,
but without Loki integration (deferred to future stages).
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


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

