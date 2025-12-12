# Style Guide

## Python Code Style

### General Guidelines
- Follow **PEP 8** style guide
- Use **type hints** for function signatures
- Maximum line length: **100 characters**
- Use **snake_case** for functions and variables
- Use **PascalCase** for classes
- Use **UPPERCASE** for constants

### Code Organization
```python
# Standard library imports
import os
from typing import Optional, List

# Third-party imports
from google.cloud import bigquery
from dotenv import load_dotenv

# Local imports
from .config import Config
from .backoff import with_backoff
```

### Documentation
- Use **docstrings** for all public functions and classes
- Follow **Google docstring style**
- Include type information in docstrings

Example:
```python
def fetch_quotes(
    symbol: str,
    timeframe: str,
    exchange: Optional[str] = None
) -> List[dict]:
    """Fetch stock quotes from BigQuery.
    
    Args:
        symbol: Stock symbol to query
        timeframe: Timeframe identifier (e.g., '1d', '1h')
        exchange: Optional exchange filter
        
    Returns:
        List of quote dictionaries with OHLCV data
        
    Raises:
        ValueError: If parameters are invalid
        BigQueryError: If query execution fails
    """
    pass
```

### Error Handling
```python
# Good: Specific exception types
try:
    result = client.query(sql)
except google.api_core.exceptions.NotFound as e:
    raise ValueError(f"Table not found: {e}")
except google.api_core.exceptions.GoogleAPIError as e:
    raise RuntimeError(f"BigQuery error: {e}")

# Bad: Bare except
try:
    result = client.query(sql)
except:
    print("Error!")
```

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Query constructed: %s", sql)
logger.info("Fetching quotes for symbol: %s", symbol)
logger.warning("Multiple exchanges found, using first: %s", exchange)
logger.error("Failed to authenticate: %s", error)
```

## Configuration Style

### Environment Variables
- Use UPPERCASE with underscores
- Prefix with project identifier
- Group related variables

```bash
# .env file
BIGQUERY_PROJECT_ID=my-project
BIGQUERY_DATASET=market_data
BIGQUERY_TABLE=quotes
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

# Backoff settings
BACKOFF_BASE=1.0
BACKOFF_FACTOR=2.0
BACKOFF_MAX=32.0
BACKOFF_ATTEMPTS=5
```

## Query Style

### SQL Formatting
```sql
-- Good: Readable, parameterized
SELECT 
    timestamp,
    open,
    high,
    low,
    close,
    volume
FROM `{project}.{dataset}.{table}`
WHERE 
    symbol = @symbol
    AND timeframe = @timeframe
    AND exchange = @exchange
ORDER BY timestamp ASC
```

## Git Practices

### Commit Messages
```
Format: <type>: <subject>

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- style: Formatting
- refactor: Code restructuring
- test: Tests
- chore: Maintenance

Example:
feat: add exponential backoff for BigQuery queries
```

### .gitignore
```
# Credentials
.env
*.json
!.env.example

# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/

# IDE
.vscode/
.idea/
*.swp
```

## Testing Style

### Test Organization
```python
# test_query_builder.py
import pytest
from src.query_builder import QueryBuilder

class TestQueryBuilder:
    def test_basic_query(self):
        """Test basic query construction."""
        builder = QueryBuilder()
        query = builder.build(symbol="BTC", timeframe="1d")
        assert "symbol = @symbol" in query
        
    def test_date_range_query(self):
        """Test query with date range."""
        builder = QueryBuilder()
        query = builder.build(
            symbol="BTC",
            timeframe="1d",
            from_date="2024-01-01",
            to_date="2024-01-31"
        )
        assert "BETWEEN" in query
```

## Documentation

### README Structure
1. Project description
2. Requirements
3. Installation
4. Configuration
5. Usage examples
6. Development setup
7. License

### Code Comments
```python
# Good: Explain why, not what
# Use first exchange when multiple exist to ensure deterministic behavior
exchange = exchanges[0]

# Bad: Redundant comment
# Get the first exchange
exchange = exchanges[0]
```

