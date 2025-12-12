"""
Error mapper for converting BigQuery exceptions to custom exceptions.

Maps google-cloud-bigquery exceptions to our custom exception hierarchy.
"""

from typing import Any, Dict, Optional

from google.api_core import exceptions as google_exceptions
from google.auth import exceptions as auth_exceptions

from .exceptions import (
    BQExtractorError,
    AuthenticationError,
    QueryExecutionError,
    NetworkError,
    ValidationError,
)


class ErrorMapper:
    """Maps BigQuery and Google Cloud exceptions to custom exceptions."""
    
    @staticmethod
    def map_exception(
        exc: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> BQExtractorError:
        """Map a caught exception to our custom exception hierarchy.
        
        Args:
            exc: Original exception
            context: Additional context to attach to the mapped exception
        
        Returns:
            Mapped custom exception
        
        Example:
            >>> try:
            ...     client.query(sql)
            ... except Exception as e:
            ...     custom_exc = ErrorMapper.map_exception(e, {"query": sql})
            ...     raise custom_exc
        """
        context = context or {}
        
        # Authentication errors
        if isinstance(exc, (auth_exceptions.DefaultCredentialsError,
                           auth_exceptions.RefreshError,
                           auth_exceptions.GoogleAuthError)):
            return AuthenticationError(
                message=f"Authentication failed: {str(exc)}",
                context={**context, "original_error": type(exc).__name__},
                retryable=False,
            )
        
        # Permission denied
        if isinstance(exc, google_exceptions.PermissionDenied):
            return AuthenticationError(
                message=f"Permission denied: {str(exc)}",
                context={**context, "original_error": "PermissionDenied"},
                retryable=False,
            )
        
        # Not found (dataset, table, project)
        if isinstance(exc, google_exceptions.NotFound):
            return QueryExecutionError(
                message=f"Resource not found: {str(exc)}. Check GCP_PROJECT_ID, BQ_DATASET, and BQ_TABLE in .env",
                context={**context, "original_error": "NotFound"},
                retryable=False,
            )
        
        # Bad request (SQL syntax errors, invalid parameters)
        if isinstance(exc, google_exceptions.BadRequest):
            return QueryExecutionError(
                message=f"Bad request: {str(exc)}",
                context={**context, "original_error": "BadRequest"},
                retryable=False,
            )
        
        # Network/timeout errors (retryable)
        if isinstance(exc, (google_exceptions.ServiceUnavailable,
                           google_exceptions.DeadlineExceeded,
                           google_exceptions.GatewayTimeout)):
            return NetworkError(
                message=f"Network error: {str(exc)}",
                context={**context, "original_error": type(exc).__name__},
                retryable=True,
            )
        
        # Resource exhausted (quota, rate limiting) - retryable with backoff
        if isinstance(exc, google_exceptions.ResourceExhausted):
            return NetworkError(
                message=f"Resource exhausted (quota/rate limit): {str(exc)}",
                context={**context, "original_error": "ResourceExhausted"},
                retryable=True,
            )
        
        # Internal server errors (retryable)
        if isinstance(exc, google_exceptions.InternalServerError):
            return NetworkError(
                message=f"BigQuery internal error: {str(exc)}",
                context={**context, "original_error": "InternalServerError"},
                retryable=True,
            )
        
        # Generic Google API error
        if isinstance(exc, google_exceptions.GoogleAPIError):
            return QueryExecutionError(
                message=f"BigQuery API error: {str(exc)}",
                context={**context, "original_error": type(exc).__name__},
                retryable=False,
            )
        
        # Unknown exception - wrap as generic query error
        return QueryExecutionError(
            message=f"Unexpected error: {str(exc)}",
            context={**context, "original_error": type(exc).__name__},
            retryable=False,
        )
    
    @staticmethod
    def is_retryable(exc: Exception) -> bool:
        """Check if an exception is retryable.
        
        Args:
            exc: Exception to check
        
        Returns:
            True if exception should trigger retry logic
        """
        # Map to custom exception and check retryable flag
        custom_exc = ErrorMapper.map_exception(exc)
        return custom_exc.retryable

