"""
Custom exception hierarchy for BigQuery Stock Quotes Extractor.

Implements structured error handling with context, exit codes, and retry flags.
Based on creative phase design decision: Custom Exception Hierarchy with Central Handler.
"""

from typing import Any, Dict, Optional


class BQExtractorError(Exception):
    """Base exception for all BigQuery extractor errors.
    
    Attributes:
        message: Human-readable error message
        context: Additional context information (dict)
        exit_code: Exit code for the script
        retryable: Whether this error should trigger retry logic
    """
    
    # Default exit code for this exception type
    DEFAULT_EXIT_CODE = 1
    
    # Default retryability (can be overridden per instance)
    DEFAULT_RETRYABLE = False
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exit_code: Optional[int] = None,
        retryable: Optional[bool] = None,
    ):
        """Initialize exception.
        
        Args:
            message: Error message
            context: Additional context (e.g., symbol, timeframe, query)
            exit_code: Override default exit code
            retryable: Override default retryability
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.exit_code = exit_code if exit_code is not None else self.DEFAULT_EXIT_CODE
        self.retryable = retryable if retryable is not None else self.DEFAULT_RETRYABLE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for structured logging.
        
        Returns:
            Dictionary representation of the exception
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "exit_code": self.exit_code,
            "retryable": self.retryable,
            "context": self.context,
        }


class ConfigurationError(BQExtractorError):
    """Configuration-related errors (missing .env, invalid values, etc.).
    
    Exit code: 1
    Retryable: No (requires user action)
    """
    
    DEFAULT_EXIT_CODE = 1
    DEFAULT_RETRYABLE = False


class AuthenticationError(BQExtractorError):
    """Authentication/authorization errors (invalid credentials, permissions).
    
    Exit code: 2
    Retryable: No (requires credential fix)
    """
    
    DEFAULT_EXIT_CODE = 2
    DEFAULT_RETRYABLE = False


class QueryExecutionError(BQExtractorError):
    """Query execution errors (syntax errors, BigQuery API errors).
    
    Exit code: 3
    Retryable: Depends on specific error (network errors are retryable)
    """
    
    DEFAULT_EXIT_CODE = 3
    DEFAULT_RETRYABLE = False  # Default to false, error mapper will set true for network errors


class NetworkError(BQExtractorError):
    """Network-related errors (timeouts, connection errors).
    
    Exit code: 3
    Retryable: Yes (transient network issues)
    """
    
    DEFAULT_EXIT_CODE = 3
    DEFAULT_RETRYABLE = True


class FileSystemError(BQExtractorError):
    """File system errors (output directory not writable, disk full).
    
    Exit code: 4
    Retryable: No (requires user action)
    """
    
    DEFAULT_EXIT_CODE = 4
    DEFAULT_RETRYABLE = False


class ValidationError(BQExtractorError):
    """Input validation errors (invalid symbol format, timeframe, etc.).
    
    Exit code: 1
    Retryable: No (requires correct input)
    """
    
    DEFAULT_EXIT_CODE = 1
    DEFAULT_RETRYABLE = False


class DataNotFoundError(BQExtractorError):
    """Data not found errors (no records matching query).
    
    Exit code: 0 (not an error condition, just empty result)
    Retryable: No
    """
    
    DEFAULT_EXIT_CODE = 0
    DEFAULT_RETRYABLE = False

