"""
Unit tests for exception handling and error mapping.
"""

import pytest

from google.api_core import exceptions as google_exceptions
from google.auth import exceptions as auth_exceptions

from src.exceptions import (
    BQExtractorError,
    ConfigurationError,
    AuthenticationError,
    QueryExecutionError,
    NetworkError,
    FileSystemError,
    ValidationError,
    DataNotFoundError,
)
from src.error_mapper import ErrorMapper


class TestBQExtractorError:
    """Test base exception class."""
    
    def test_init_with_defaults(self):
        """Test exception initialization with defaults."""
        exc = BQExtractorError("Test error")
        
        assert exc.message == "Test error"
        assert exc.context == {}
        assert exc.exit_code == 1
        assert exc.retryable is False
    
    def test_init_with_context(self):
        """Test exception initialization with context."""
        context = {"symbol": "BTCUSDT", "timeframe": "1d"}
        exc = BQExtractorError("Test error", context=context)
        
        assert exc.context == context
    
    def test_init_with_overrides(self):
        """Test exception initialization with overrides."""
        exc = BQExtractorError(
            "Test error",
            context={"key": "value"},
            exit_code=99,
            retryable=True,
        )
        
        assert exc.exit_code == 99
        assert exc.retryable is True
    
    def test_to_dict(self):
        """Test exception to_dict conversion."""
        exc = BQExtractorError(
            "Test error",
            context={"symbol": "BTCUSDT"},
            exit_code=1,
            retryable=False,
        )
        
        data = exc.to_dict()
        
        assert data["error_type"] == "BQExtractorError"
        assert data["message"] == "Test error"
        assert data["exit_code"] == 1
        assert data["retryable"] is False
        assert data["context"]["symbol"] == "BTCUSDT"


class TestExceptionTypes:
    """Test specific exception types."""
    
    def test_configuration_error(self):
        """Test ConfigurationError defaults."""
        exc = ConfigurationError("Config error")
        
        assert exc.exit_code == 1
        assert exc.retryable is False
    
    def test_authentication_error(self):
        """Test AuthenticationError defaults."""
        exc = AuthenticationError("Auth error")
        
        assert exc.exit_code == 2
        assert exc.retryable is False
    
    def test_query_execution_error(self):
        """Test QueryExecutionError defaults."""
        exc = QueryExecutionError("Query error")
        
        assert exc.exit_code == 3
        assert exc.retryable is False
    
    def test_network_error(self):
        """Test NetworkError defaults."""
        exc = NetworkError("Network error")
        
        assert exc.exit_code == 3
        assert exc.retryable is True  # Network errors are retryable
    
    def test_filesystem_error(self):
        """Test FileSystemError defaults."""
        exc = FileSystemError("Filesystem error")
        
        assert exc.exit_code == 4
        assert exc.retryable is False
    
    def test_validation_error(self):
        """Test ValidationError defaults."""
        exc = ValidationError("Validation error")
        
        assert exc.exit_code == 1
        assert exc.retryable is False
    
    def test_data_not_found_error(self):
        """Test DataNotFoundError defaults."""
        exc = DataNotFoundError("No data")
        
        assert exc.exit_code == 0  # Not really an error
        assert exc.retryable is False


class TestErrorMapper:
    """Test error mapper."""
    
    def test_map_authentication_error(self):
        """Test mapping of authentication errors."""
        original = auth_exceptions.DefaultCredentialsError("Credentials not found")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, AuthenticationError)
        assert "Authentication failed" in mapped.message
        assert mapped.retryable is False
    
    def test_map_permission_denied(self):
        """Test mapping of permission denied error."""
        original = google_exceptions.PermissionDenied("Access denied")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, AuthenticationError)
        assert "Permission denied" in mapped.message
        assert mapped.retryable is False
    
    def test_map_not_found(self):
        """Test mapping of not found error."""
        original = google_exceptions.NotFound("Table not found")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, QueryExecutionError)
        assert "Resource not found" in mapped.message
        assert mapped.retryable is False
    
    def test_map_bad_request(self):
        """Test mapping of bad request error."""
        original = google_exceptions.BadRequest("Invalid SQL")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, QueryExecutionError)
        assert "Bad request" in mapped.message
        assert mapped.retryable is False
    
    def test_map_service_unavailable(self):
        """Test mapping of service unavailable error (retryable)."""
        original = google_exceptions.ServiceUnavailable("Service unavailable")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, NetworkError)
        assert "Network error" in mapped.message
        assert mapped.retryable is True
    
    def test_map_deadline_exceeded(self):
        """Test mapping of deadline exceeded error (retryable)."""
        original = google_exceptions.DeadlineExceeded("Timeout")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, NetworkError)
        assert "Network error" in mapped.message
        assert mapped.retryable is True
    
    def test_map_resource_exhausted(self):
        """Test mapping of resource exhausted error (retryable)."""
        original = google_exceptions.ResourceExhausted("Quota exceeded")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, NetworkError)
        assert "Resource exhausted" in mapped.message
        assert mapped.retryable is True
    
    def test_map_internal_server_error(self):
        """Test mapping of internal server error (retryable)."""
        original = google_exceptions.InternalServerError("Internal error")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, NetworkError)
        assert "BigQuery internal error" in mapped.message
        assert mapped.retryable is True
    
    def test_map_with_context(self):
        """Test mapping preserves context."""
        original = google_exceptions.BadRequest("Error")
        context = {"symbol": "BTCUSDT", "query": "SELECT *"}
        mapped = ErrorMapper.map_exception(original, context=context)
        
        assert mapped.context["symbol"] == "BTCUSDT"
        assert mapped.context["query"] == "SELECT *"
    
    def test_is_retryable_true(self):
        """Test is_retryable returns True for retryable errors."""
        original = google_exceptions.ServiceUnavailable("Service unavailable")
        
        assert ErrorMapper.is_retryable(original) is True
    
    def test_is_retryable_false(self):
        """Test is_retryable returns False for non-retryable errors."""
        original = google_exceptions.BadRequest("Bad request")
        
        assert ErrorMapper.is_retryable(original) is False
    
    def test_map_unknown_exception(self):
        """Test mapping of unknown exception type."""
        original = ValueError("Some random error")
        mapped = ErrorMapper.map_exception(original)
        
        assert isinstance(mapped, QueryExecutionError)
        assert "Unexpected error" in mapped.message
        assert mapped.retryable is False

