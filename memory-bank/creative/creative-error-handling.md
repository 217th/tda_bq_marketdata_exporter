# Creative Phase: Error Handling Strategy

**Component**: Cross-cutting error handling architecture  
**Type**: System Design  
**Date**: 2025-12-11  
**Status**: ✅ Complete

---

## Problem Statement

Design a comprehensive error handling strategy for the BigQuery stock quotes extractor that:
1. Distinguishes between recoverable and non-recoverable errors
2. Provides clear, actionable feedback to users
3. Logs sufficient technical detail for debugging
4. Integrates with structured logging system
5. Supports exponential backoff retry logic
6. Handles all failure scenarios gracefully

### Key Challenges:
- **Multiple Error Sources**: Configuration, authentication, network, BigQuery API, filesystem
- **User vs Developer Needs**: Clear messages for users, detailed logs for debugging
- **Retry Logic**: Some errors should trigger backoff, others should fail immediately
- **Exit Codes**: Script must return appropriate exit codes for automation
- **Structured Logging**: Must integrate with existing JSON logging pattern

---

## Requirements

### Functional Requirements
1. **Error Classification**
   - Distinguish retryable vs non-retryable errors
   - Identify error source (config, auth, query, network, filesystem)
   - Map BigQuery exceptions to appropriate categories

2. **User Communication**
   - Clear, actionable error messages on failure
   - Progress indication during retries
   - Helpful suggestions for common issues

3. **Logging Integration**
   - All errors logged with structured JSON format
   - Include context: symbol, timeframe, query mode
   - Technical details for debugging (stack traces when needed)

4. **Exit Codes**
   - 0: Success
   - 1: General error (config, validation)
   - 2: Authentication error
   - 3: BigQuery error (non-retryable)
   - 4: File I/O error
   - 5: No data found (optional: treat as success with warning)

### Technical Requirements
- Integration with `logging_util.py` structured logging
- Support for backoff decorator in `backoff.py`
- No external exception libraries (use standard Python)
- Type hints for exception parameters

### Quality Requirements
- **Maintainability**: Easy to add new error types
- **Testability**: Errors can be simulated for testing
- **Performance**: Minimal overhead on happy path
- **Clarity**: Error messages understandable by non-developers

---

## Design Options

### Option 1: Flat Exception Handling (Try/Except in Each Module)

**Description**: Each module handles its own exceptions with try/except blocks, no custom exception hierarchy.

```python
# config.py
def load_config():
    try:
        load_dotenv()
        project = os.getenv("BIGQUERY_PROJECT_ID")
        if not project:
            raise ValueError("BIGQUERY_PROJECT_ID not set")
    except ValueError as e:
        logger.error({"message": "Configuration error", "error": str(e)})
        sys.exit(1)

# bigquery_client.py
def execute_query(sql):
    try:
        results = client.query(sql).result()
        return list(results)
    except google.api_core.exceptions.NotFound:
        logger.error({"message": "Table not found"})
        sys.exit(3)
    except Exception as e:
        logger.error({"message": "Query failed", "error": str(e)})
        sys.exit(3)
```

**Pros:**
- ✅ Simple, no custom classes
- ✅ Fast to implement
- ✅ Easy to understand for beginners
- ✅ Direct control flow

**Cons:**
- ❌ Error handling logic scattered
- ❌ Hard to centralize logging
- ❌ Difficult to distinguish error types programmatically
- ❌ Exit codes hardcoded everywhere
- ❌ Can't easily mock errors for testing

**Complexity**: Low (30 min implementation)

---

### Option 2: Custom Exception Hierarchy with Central Handler

**Description**: Define custom exception classes, raise them throughout code, catch centrally in main.

```python
# exceptions.py
class BQExtractorError(Exception):
    """Base exception for extractor."""
    exit_code = 1
    retryable = False

class ConfigurationError(BQExtractorError):
    """Configuration missing or invalid."""
    exit_code = 1

class AuthenticationError(BQExtractorError):
    """GCP authentication failed."""
    exit_code = 2

class QueryError(BQExtractorError):
    """BigQuery query failed."""
    exit_code = 3
    retryable = True  # May be retryable depending on subtype

class NoDataFoundError(BQExtractorError):
    """No data returned from query."""
    exit_code = 5
    retryable = False

class FileOutputError(BQExtractorError):
    """Failed to write output file."""
    exit_code = 4

# Usage in modules
def load_config():
    if not os.getenv("BIGQUERY_PROJECT_ID"):
        raise ConfigurationError("BIGQUERY_PROJECT_ID not set in .env")

# main.py
def main():
    try:
        config = load_config()
        client = create_client(config)
        data = execute_query(client, query)
        save_output(data)
    except BQExtractorError as e:
        log_struct(logger, env_labels(), {
            "message": "Fatal error",
            "error_type": type(e).__name__,
            "error": str(e),
        })
        sys.exit(e.exit_code)
```

**Pros:**
- ✅ Centralized error handling in main
- ✅ Clean separation of concerns
- ✅ Easy to add new error types
- ✅ Exit codes attached to exceptions
- ✅ Testable (can raise specific errors in tests)
- ✅ Type-safe with type hints

**Cons:**
- ❌ More boilerplate code
- ❌ Need to define exception hierarchy upfront
- ❌ May need to wrap third-party exceptions

**Complexity**: Medium (1 hour implementation)

---

### Option 3: Result Objects (Railway-Oriented Programming)

**Description**: Functions return `Result[T, Error]` objects instead of raising exceptions.

```python
# result.py
from typing import Generic, TypeVar, Union
from dataclasses import dataclass

T = TypeVar('T')
E = TypeVar('E')

@dataclass
class Success(Generic[T]):
    value: T

@dataclass
class Failure(Generic[E]):
    error: E
    exit_code: int

Result = Union[Success[T], Failure[E]]

# Usage
def load_config() -> Result[Config, str]:
    if not os.getenv("BIGQUERY_PROJECT_ID"):
        return Failure("BIGQUERY_PROJECT_ID not set", exit_code=1)
    return Success(Config(...))

def main():
    config_result = load_config()
    if isinstance(config_result, Failure):
        log_error(config_result.error)
        sys.exit(config_result.exit_code)
    
    config = config_result.value
    # Continue with config...
```

**Pros:**
- ✅ Explicit error handling (no hidden exceptions)
- ✅ Type-safe (mypy can verify all error paths handled)
- ✅ Functional programming style
- ✅ Easy to chain operations

**Cons:**
- ❌ Unfamiliar to most Python developers
- ❌ Verbose (need to check every result)
- ❌ Doesn't integrate well with third-party libraries (BigQuery raises exceptions)
- ❌ Overhead of wrapping all operations
- ❌ Difficult for beginners

**Complexity**: High (2+ hours implementation, learning curve)

---

### Option 4: Hybrid Approach (Custom Exceptions + Error Context Decorator)

**Description**: Custom exception hierarchy + decorator that adds context and handles logging.

```python
# exceptions.py
class BQExtractorError(Exception):
    exit_code = 1
    retryable = False
    
    def __init__(self, message: str, **context):
        super().__init__(message)
        self.message = message
        self.context = context

class ConfigurationError(BQExtractorError):
    exit_code = 1

class QueryError(BQExtractorError):
    exit_code = 3
    retryable = True

# error_handler.py
def with_error_context(**default_context):
    """Decorator that enriches errors with context."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BQExtractorError as e:
                # Add context
                e.context.update(default_context)
                raise
            except google.api_core.exceptions.NotFound as e:
                raise QueryError("Table not found", **default_context) from e
            except google.api_core.exceptions.Forbidden as e:
                raise AuthenticationError("Access denied", **default_context) from e
        return wrapper
    return decorator

# Usage
@with_error_context(component="bigquery_client")
def execute_query(sql: str, symbol: str, timeframe: str):
    try:
        results = client.query(sql).result()
        return list(results)
    except google.api_core.exceptions.NotFound:
        raise QueryError(
            f"Table not found",
            symbol=symbol,
            timeframe=timeframe,
        )

# main.py
def main():
    try:
        # ... application logic ...
    except BQExtractorError as e:
        log_struct(logger, env_labels(), {
            "message": e.message,
            "error_type": type(e).__name__,
            "exit_code": e.exit_code,
            **e.context,
        })
        sys.exit(e.exit_code)
```

**Pros:**
- ✅ Best of both: structure + convenience
- ✅ Automatic context enrichment
- ✅ Clean module code
- ✅ Integrates well with structured logging
- ✅ Can wrap third-party exceptions gracefully
- ✅ Testable and maintainable

**Cons:**
- ❌ Slightly more complex than Option 2
- ❌ Decorator pattern may be unfamiliar
- ❌ Need to define context schemas

**Complexity**: Medium-High (1.5 hours implementation)

---

## Architecture Decision

### 🏆 Selected Approach: **Option 2 - Custom Exception Hierarchy with Central Handler**

**Rationale:**

**Why Option 2:**
1. **Simplicity vs Power Balance**: Provides structure without excessive complexity
2. **Pythonic**: Exceptions are the standard error handling mechanism in Python
3. **Integration**: Works seamlessly with existing backoff decorator and BigQuery library
4. **Maintainability**: Easy to extend with new error types
5. **No Learning Curve**: Standard Python exception handling patterns
6. **Testing**: Easy to mock and raise specific errors in tests
7. **Clear Exit Codes**: Exit codes attached to exception classes (DRY principle)

**Why Not Option 1:**
- Too scattered, hard to maintain as project grows
- No programmatic distinction between error types
- Exit codes hardcoded throughout codebase

**Why Not Option 3:**
- Not idiomatic Python
- Verbose and unfamiliar to most developers
- Poor integration with third-party libraries (BigQuery)
- Overkill for a script-based application

**Why Not Option 4:**
- Over-engineered for current scope
- Decorator adds complexity without significant benefit
- Context can be added to exceptions directly in Option 2
- Can evolve to Option 4 if needed in future

---

## Implementation Plan

### Phase 1: Exception Hierarchy (20 min)

**File**: `src/exceptions.py`

```python
"""Custom exceptions for BigQuery extractor."""

class BQExtractorError(Exception):
    """Base exception for all extractor errors."""
    exit_code: int = 1
    retryable: bool = False
    
    def __init__(self, message: str, **context):
        super().__init__(message)
        self.message = message
        self.context = context


class ConfigurationError(BQExtractorError):
    """Configuration missing or invalid."""
    exit_code = 1
    
    
class AuthenticationError(BQExtractorError):
    """GCP authentication failed."""
    exit_code = 2


class ValidationError(BQExtractorError):
    """Input validation failed."""
    exit_code = 1


class QueryExecutionError(BQExtractorError):
    """BigQuery query execution failed (non-retryable)."""
    exit_code = 3
    retryable = False


class QueryTimeoutError(BQExtractorError):
    """BigQuery query timed out (retryable)."""
    exit_code = 3
    retryable = True


class RateLimitError(BQExtractorError):
    """BigQuery rate limit exceeded (retryable)."""
    exit_code = 3
    retryable = True


class NetworkError(BQExtractorError):
    """Network communication failed (retryable)."""
    exit_code = 3
    retryable = True


class NoDataFoundError(BQExtractorError):
    """No data returned from query (not an error, but logged)."""
    exit_code = 0  # Success with warning
    

class FileOutputError(BQExtractorError):
    """Failed to write output file."""
    exit_code = 4
```

**Deliverable**: Exception hierarchy complete

---

### Phase 2: Error Mapping Utilities (20 min)

**File**: `src/error_mapper.py`

```python
"""Map third-party exceptions to custom exceptions."""
import google.api_core.exceptions
from .exceptions import (
    AuthenticationError,
    QueryExecutionError,
    QueryTimeoutError,
    RateLimitError,
    NetworkError,
)


def map_bigquery_error(e: Exception, **context) -> Exception:
    """Convert BigQuery exceptions to custom exceptions with context.
    
    Args:
        e: Original BigQuery exception
        **context: Additional context (symbol, timeframe, etc.)
        
    Returns:
        Custom exception with context
    """
    # Authentication errors
    if isinstance(e, (
        google.api_core.exceptions.Unauthenticated,
        google.api_core.exceptions.Forbidden,
    )):
        return AuthenticationError(
            f"Authentication failed: {str(e)}",
            original_error=type(e).__name__,
            **context,
        )
    
    # Rate limiting
    if isinstance(e, google.api_core.exceptions.TooManyRequests):
        return RateLimitError(
            f"BigQuery rate limit exceeded: {str(e)}",
            original_error=type(e).__name__,
            **context,
        )
    
    # Timeouts
    if isinstance(e, google.api_core.exceptions.DeadlineExceeded):
        return QueryTimeoutError(
            f"Query timed out: {str(e)}",
            original_error=type(e).__name__,
            **context,
        )
    
    # Network errors
    if isinstance(e, (
        google.api_core.exceptions.ServerError,
        google.api_core.exceptions.ServiceUnavailable,
    )):
        return NetworkError(
            f"Network error: {str(e)}",
            original_error=type(e).__name__,
            **context,
        )
    
    # Bad request / query errors
    if isinstance(e, google.api_core.exceptions.BadRequest):
        return QueryExecutionError(
            f"Invalid query: {str(e)}",
            original_error=type(e).__name__,
            **context,
        )
    
    # Table/resource not found
    if isinstance(e, google.api_core.exceptions.NotFound):
        return QueryExecutionError(
            f"Resource not found: {str(e)}",
            original_error=type(e).__name__,
            **context,
        )
    
    # Default: non-retryable query error
    return QueryExecutionError(
        f"BigQuery error: {str(e)}",
        original_error=type(e).__name__,
        **context,
    )
```

**Deliverable**: Error mapping complete

---

### Phase 3: Central Error Handler (20 min)

**File**: `main.py` (error handling section)

```python
"""Main entry point with central error handling."""
import sys
from src.logging_util import build_logger, log_struct, env_labels
from src.exceptions import BQExtractorError, NoDataFoundError


def main():
    """Main execution with centralized error handling."""
    logger = None
    
    try:
        # Initialize logger first (may raise ConfigurationError)
        logger = build_logger(
            service_name=os.getenv("SERVICE_NAME", "bigquery-extractor"),
            environment=os.getenv("ENVIRONMENT", "dev"),
        )
        
        log_struct(logger, env_labels(), {
            "message": "Starting BigQuery extraction",
        })
        
        # Load configuration
        config = load_config()
        
        # Parse arguments
        args = parse_arguments()
        
        # Validate inputs
        validate_inputs(args)
        
        # Create BigQuery client
        client = create_bigquery_client(config)
        
        # Build query
        query = build_query(args)
        
        # Execute with backoff
        results = execute_query(client, query, args.symbol, args.timeframe)
        
        # Handle empty results
        if not results:
            raise NoDataFoundError(
                "No data found for specified parameters",
                symbol=args.symbol,
                timeframe=args.timeframe,
                query_mode=args.query_mode,
            )
        
        # Save output
        output_path = save_output(results, args)
        
        log_struct(logger, env_labels(), {
            "message": "Extraction completed successfully",
            "symbol": args.symbol,
            "timeframe": args.timeframe,
            "records": len(results),
            "output_file": output_path,
        })
        
        sys.exit(0)
        
    except NoDataFoundError as e:
        # Special case: no data is warning, not error
        if logger:
            log_struct(logger, env_labels(), {
                "message": e.message,
                "level": "warning",
                "error_type": type(e).__name__,
                **e.context,
            })
        print(f"Warning: {e.message}", file=sys.stderr)
        sys.exit(e.exit_code)  # 0 (success with warning)
        
    except BQExtractorError as e:
        # All custom exceptions
        if logger:
            log_struct(logger, env_labels(), {
                "message": e.message,
                "level": "error",
                "error_type": type(e).__name__,
                "exit_code": e.exit_code,
                "retryable": e.retryable,
                **e.context,
            })
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(e.exit_code)
        
    except KeyboardInterrupt:
        if logger:
            log_struct(logger, env_labels(), {
                "message": "Interrupted by user",
                "level": "info",
            })
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)  # Standard SIGINT exit code
        
    except Exception as e:
        # Unexpected errors
        if logger:
            log_struct(logger, env_labels(), {
                "message": "Unexpected error",
                "level": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            })
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Deliverable**: Central error handler complete

---

### Phase 4: Module Integration (20 min)

Update each module to raise custom exceptions:

**config.py**:
```python
from .exceptions import ConfigurationError

def load_config():
    load_dotenv()
    
    required = [
        "BIGQUERY_PROJECT_ID",
        "BIGQUERY_DATASET",
        "BIGQUERY_TABLE",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ]
    
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing)}",
            missing_vars=missing,
        )
    
    # ... return config
```

**bigquery_client.py**:
```python
from .exceptions import AuthenticationError
from .error_mapper import map_bigquery_error

def create_client(config):
    try:
        credentials = service_account.Credentials.from_service_account_file(
            config.credentials_path
        )
        return bigquery.Client(
            credentials=credentials,
            project=config.project_id,
        )
    except FileNotFoundError as e:
        raise AuthenticationError(
            f"Credentials file not found: {config.credentials_path}",
            credentials_path=config.credentials_path,
        ) from e
    except Exception as e:
        raise AuthenticationError(
            f"Failed to create BigQuery client: {str(e)}",
            credentials_path=config.credentials_path,
        ) from e

@with_backoff  # Backoff decorator handles retryable errors
def execute_query(client, sql, symbol, timeframe):
    try:
        query_job = client.query(sql)
        results = list(query_job.result())
        return results
    except Exception as e:
        # Map to custom exception
        raise map_bigquery_error(
            e,
            symbol=symbol,
            timeframe=timeframe,
            query=sql[:200],  # First 200 chars
        ) from e
```

**output_handler.py**:
```python
from .exceptions import FileOutputError

def save_output(data, output_path):
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return output_path
    except PermissionError as e:
        raise FileOutputError(
            f"Permission denied writing to {output_path}",
            output_path=output_path,
        ) from e
    except IOError as e:
        raise FileOutputError(
            f"Failed to write output file: {str(e)}",
            output_path=output_path,
        ) from e
```

**Deliverable**: All modules integrated

---

### Phase 5: Backoff Integration (10 min)

Update `backoff.py` to recognize retryable exceptions:

```python
from .exceptions import BQExtractorError

def with_backoff(func):
    """Decorator for exponential backoff on retryable errors."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        attempt = 0
        delay = BACKOFF_BASE
        
        while attempt < BACKOFF_ATTEMPTS:
            try:
                return func(*args, **kwargs)
            except BQExtractorError as e:
                if not e.retryable or attempt >= BACKOFF_ATTEMPTS - 1:
                    raise  # Non-retryable or max attempts reached
                
                attempt += 1
                log_struct(logger, env_labels(), {
                    "message": "Retrying after error",
                    "attempt": attempt,
                    "delay_seconds": delay,
                    "error": e.message,
                })
                
                time.sleep(delay)
                delay = min(delay * BACKOFF_FACTOR, BACKOFF_MAX)
            except Exception as e:
                # Non-custom exceptions: don't retry
                raise
    
    return wrapper
```

**Deliverable**: Backoff recognizes retryable errors

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          Central Error Handler (try/except)           │  │
│  │  - Catches all BQExtractorError                       │  │
│  │  - Logs structured JSON                               │  │
│  │  - Returns appropriate exit code                      │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────┬─────────────────────────────────────────┘
                    │ raises
┌───────────────────┴─────────────────────────────────────────┐
│                   src/exceptions.py                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              BQExtractorError (base)                │    │
│  │  - message: str                                     │    │
│  │  - context: Dict[str, Any]                          │    │
│  │  - exit_code: int                                   │    │
│  │  - retryable: bool                                  │    │
│  └─────────────────────────────────────────────────────┘    │
│       ▲        ▲         ▲           ▲            ▲         │
│       │        │         │           │            │         │
│   Config  Auth   Validation   QueryExecution  FileOutput   │
│   Error   Error    Error          Error         Error      │
└─────────────────────────────────────────────────────────────┘
                    ▲
                    │ converts
┌───────────────────┴─────────────────────────────────────────┐
│                src/error_mapper.py                          │
│  map_bigquery_error(exception, **context)                   │
│  - Maps google.api_core.exceptions.*                        │
│  - To custom exceptions with context                        │
└─────────────────────────────────────────────────────────────┘
                    ▲
                    │ raises original
┌───────────────────┴─────────────────────────────────────────┐
│          BigQuery Client / Google API                       │
│  - NotFound, Forbidden, BadRequest, etc.                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Error Flow Diagram

```
┌──────────────┐
│  User runs   │
│    script    │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│  main() - try block                              │
│  ┌────────────────────────────────────────────┐  │
│  │ 1. Load config                             │  │
│  │    → ConfigurationError if .env missing    │──┼──► Exit 1
│  ├────────────────────────────────────────────┤  │
│  │ 2. Validate inputs                         │  │
│  │    → ValidationError if invalid symbol     │──┼──► Exit 1
│  ├────────────────────────────────────────────┤  │
│  │ 3. Create BigQuery client                  │  │
│  │    → AuthenticationError if key invalid    │──┼──► Exit 2
│  ├────────────────────────────────────────────┤  │
│  │ 4. Execute query (with backoff)            │  │
│  │    → RateLimitError (retryable)            │──┼──┐
│  │    → NetworkError (retryable)              │──┼──┤
│  │    → QueryTimeoutError (retryable)         │──┼──┼─► Retry
│  │    → QueryExecutionError (not retryable)   │──┼──┼─► Exit 3
│  ├────────────────────────────────────────────┤  │  │
│  │ 5. Check results                           │  │  │
│  │    → NoDataFoundError if empty             │──┼──┼─► Exit 0 (warning)
│  ├────────────────────────────────────────────┤  │  │
│  │ 6. Save output                             │  │  │
│  │    → FileOutputError if write fails        │──┼──┼─► Exit 4
│  └────────────────────────────────────────────┘  │  │
└──────────────────────────────────────────────────┘  │
                                                      │
       ┌──────────────────────────────────────────────┘
       │
       ▼
┌──────────────────┐        ┌─────────────────────────┐
│  Backoff logic   │  Yes   │  Retry with exponential │
│  retryable?      │───────►│  delay                  │
└──────┬───────────┘        └────────────┬────────────┘
       │ No                              │
       │                                 └──► Back to execute_query
       ▼
┌──────────────────┐
│  Log error       │
│  (JSON struct)   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Print to stderr │
│  (user message)  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  sys.exit(code)  │
└──────────────────┘
```

---

## Error Message Examples

### Configuration Error
**Console**:
```
Error: Missing required environment variables: BIGQUERY_PROJECT_ID, BIGQUERY_DATASET
```

**Log** (JSON):
```json
{
  "message": "Missing required environment variables: BIGQUERY_PROJECT_ID, BIGQUERY_DATASET",
  "level": "error",
  "error_type": "ConfigurationError",
  "exit_code": 1,
  "retryable": false,
  "missing_vars": ["BIGQUERY_PROJECT_ID", "BIGQUERY_DATASET"],
  "label_service_name": "bigquery-extractor",
  "label_environment": "dev"
}
```

---

### Authentication Error
**Console**:
```
Error: Credentials file not found: /path/to/key.json
```

**Log** (JSON):
```json
{
  "message": "Credentials file not found: /path/to/key.json",
  "level": "error",
  "error_type": "AuthenticationError",
  "exit_code": 2,
  "retryable": false,
  "credentials_path": "/path/to/key.json",
  "label_service_name": "bigquery-extractor",
  "label_environment": "dev"
}
```

---

### Rate Limit (with retry)
**Console**: (nothing printed during retries)

**Log** (JSON, retry attempt):
```json
{
  "message": "Retrying after error",
  "attempt": 1,
  "delay_seconds": 1.0,
  "error": "BigQuery rate limit exceeded: 429 Too Many Requests",
  "label_service_name": "bigquery-extractor",
  "label_environment": "dev"
}
```

---

### No Data Found
**Console**:
```
Warning: No data found for specified parameters
```

**Log** (JSON):
```json
{
  "message": "No data found for specified parameters",
  "level": "warning",
  "error_type": "NoDataFoundError",
  "symbol": "BTCUSDT",
  "timeframe": "1d",
  "query_mode": "range",
  "label_service_name": "bigquery-extractor",
  "label_environment": "dev"
}
```

---

## Testing Strategy

### Unit Tests for Exceptions
```python
def test_exception_attributes():
    """Test that exceptions have correct attributes."""
    err = ConfigurationError("Test error", foo="bar")
    assert err.exit_code == 1
    assert err.retryable == False
    assert err.message == "Test error"
    assert err.context == {"foo": "bar"}

def test_error_mapping():
    """Test BigQuery exception mapping."""
    bq_error = google.api_core.exceptions.NotFound("Table not found")
    custom = map_bigquery_error(bq_error, symbol="BTCUSDT")
    
    assert isinstance(custom, QueryExecutionError)
    assert custom.context["symbol"] == "BTCUSDT"
    assert "Table not found" in custom.message
```

### Integration Tests
```python
def test_main_handles_config_error(monkeypatch):
    """Test that main catches ConfigurationError."""
    monkeypatch.delenv("BIGQUERY_PROJECT_ID", raising=False)
    
    with pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code == 1  # ConfigurationError exit code

def test_main_handles_auth_error(tmp_path):
    """Test that main catches AuthenticationError."""
    # Set invalid credentials path
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/invalid/path.json")
    
    with pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code == 2  # AuthenticationError exit code
```

---

## Validation Against Requirements

### ✅ Functional Requirements
- [x] **Error Classification**: Exception hierarchy provides clear categories
- [x] **User Communication**: Clear messages printed to stderr
- [x] **Logging Integration**: All errors logged with structured JSON
- [x] **Exit Codes**: Attached to exception classes

### ✅ Technical Requirements
- [x] **Structured Logging**: Uses `log_struct()` from `logging_util.py`
- [x] **Backoff Integration**: `retryable` attribute checked by decorator
- [x] **No External Libraries**: Standard Python exceptions only
- [x] **Type Hints**: All exception parameters typed

### ✅ Quality Requirements
- [x] **Maintainability**: Easy to add new exception types (inherit from base)
- [x] **Testability**: Exceptions can be raised and caught in tests
- [x] **Performance**: Minimal overhead (exceptions only on error path)
- [x] **Clarity**: Error messages are clear and actionable

---

## Implementation Checklist

- [ ] Create `src/exceptions.py` with exception hierarchy
- [ ] Create `src/error_mapper.py` with BigQuery error mapping
- [ ] Update `main.py` with central error handler
- [ ] Update `config.py` to raise ConfigurationError
- [ ] Update `bigquery_client.py` to raise AuthenticationError and use error mapper
- [ ] Update `query_builder.py` to raise ValidationError for invalid inputs
- [ ] Update `output_handler.py` to raise FileOutputError
- [ ] Update `backoff.py` to check `retryable` attribute
- [ ] Write unit tests for exceptions
- [ ] Write integration tests for error handling
- [ ] Document error codes in README

---

## Summary

**Selected Architecture**: Custom Exception Hierarchy with Central Handler (Option 2)

**Key Design Decisions**:
1. **Exception Hierarchy**: Base class `BQExtractorError` with specific subclasses
2. **Exit Codes**: Attached to exception classes (1=config, 2=auth, 3=query, 4=file)
3. **Context**: Exceptions carry context dict for structured logging
4. **Retryable Flag**: Boolean flag determines if backoff should retry
5. **Error Mapping**: Separate utility converts BigQuery exceptions to custom exceptions
6. **Central Handler**: Single try/except block in main.py handles all errors
7. **Structured Logging**: All errors logged with JSON format via `log_struct()`

**Rationale**:
- Pythonic and idiomatic (exceptions are standard in Python)
- Simple to implement and maintain (~1 hour)
- Easy to test (mock exceptions)
- Clear separation of concerns
- Integrates seamlessly with backoff decorator and structured logging
- Extensible (easy to add new exception types)

**Implementation Time**: ~1.5 hours (20 min per phase × 5 phases)

---

## 🎨🎨🎨 CREATIVE PHASE COMPLETE

**Status**: ✅ Ready for BUILD mode

**Next Steps**: Implement exception hierarchy and error handling during BUILD phase.


