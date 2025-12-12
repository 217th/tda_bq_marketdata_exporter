"""
Query builder for BigQuery SQL query construction.

Implements hybrid string template approach with validator and helpers.
Supports three query modes: ALL, RANGE, NEIGHBORHOOD.
"""

from datetime import datetime
from typing import Optional

from .query_helpers import (
    calculate_adaptive_window,
    build_exchange_clause,
    format_timestamp_for_bigquery,
    calculate_default_time_range,
)
from .query_validator import QueryValidator, QueryValidationError


class QueryBuilder:
    """Builds parameterized BigQuery SQL queries for stock quotes extraction."""
    
    def __init__(self, table_fqn: str):
        """Initialize query builder.
        
        Args:
            table_fqn: Fully qualified BigQuery table name (project.dataset.table)
        """
        self.table_fqn = table_fqn
        self.validator = QueryValidator()
    
    def build_all_query(
        self,
        symbol: str,
        timeframe: str,
        exchange: Optional[str] = None,
    ) -> str:
        """Build query to fetch all historical data (15 years).
        
        Args:
            symbol: Stock symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe identifier (e.g., '1d', '1h', '15')
            exchange: Optional exchange identifier
        
        Returns:
            SQL query string
        
        Raises:
            QueryValidationError: If generated query fails validation
        
        Example:
            >>> builder = QueryBuilder('project.dataset.table')
            >>> query = builder.build_all_query('BTCUSDT', '1d')
        """
        # Calculate 15-year time range
        start_time, end_time = calculate_default_time_range(years=15)
        
        # Build exchange clause
        exchange_clause = build_exchange_clause(exchange)
        
        # Format timestamps
        start_ts = format_timestamp_for_bigquery(start_time)
        end_ts = format_timestamp_for_bigquery(end_time)
        
        # Construct query
        query = f"""
SELECT
    timestamp,
    open,
    high,
    low,
    close,
    volume
FROM
    `{self.table_fqn}`
WHERE
    symbol = '{symbol}'
    AND timeframe = '{timeframe}'
    AND timestamp >= TIMESTAMP '{start_ts}'
    AND timestamp <= TIMESTAMP '{end_ts}'
    {exchange_clause}
ORDER BY
    timestamp ASC
""".strip()
        
        # Validate query before returning
        self.validator.validate_query(query, symbol, timeframe, exchange)
        
        return query
    
    def build_range_query(
        self,
        symbol: str,
        timeframe: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
        exchange: Optional[str] = None,
    ) -> str:
        """Build query to fetch data within a specific time range.
        
        Args:
            symbol: Stock symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe identifier (e.g., '1d', '1h', '15')
            from_timestamp: Start of time range (inclusive)
            to_timestamp: End of time range (inclusive)
            exchange: Optional exchange identifier
        
        Returns:
            SQL query string
        
        Raises:
            QueryValidationError: If generated query fails validation
            ValueError: If from_timestamp > to_timestamp
        
        Example:
            >>> from datetime import datetime, timezone
            >>> builder = QueryBuilder('project.dataset.table')
            >>> start = datetime(2024, 1, 1, tzinfo=timezone.utc)
            >>> end = datetime(2024, 12, 31, tzinfo=timezone.utc)
            >>> query = builder.build_range_query('BTCUSDT', '1d', start, end)
        """
        # Validate time range
        if from_timestamp > to_timestamp:
            raise ValueError(
                f"Invalid time range: from_timestamp ({from_timestamp}) "
                f"must be <= to_timestamp ({to_timestamp})"
            )
        
        # Build exchange clause
        exchange_clause = build_exchange_clause(exchange)
        
        # Format timestamps
        from_ts = format_timestamp_for_bigquery(from_timestamp)
        to_ts = format_timestamp_for_bigquery(to_timestamp)
        
        # Construct query
        query = f"""
SELECT
    timestamp,
    open,
    high,
    low,
    close,
    volume
FROM
    `{self.table_fqn}`
WHERE
    symbol = '{symbol}'
    AND timeframe = '{timeframe}'
    AND timestamp >= TIMESTAMP '{from_ts}'
    AND timestamp <= TIMESTAMP '{to_ts}'
    {exchange_clause}
ORDER BY
    timestamp ASC
""".strip()
        
        # Validate query before returning
        self.validator.validate_query(query, symbol, timeframe, exchange)
        
        return query
    
    def build_neighborhood_query(
        self,
        symbol: str,
        timeframe: str,
        center_timestamp: datetime,
        n_before: int,
        n_after: int,
        exchange: Optional[str] = None,
    ) -> str:
        """Build query to fetch N records before and after a center timestamp.
        
        Uses UNION ALL strategy to fetch exact record counts with adaptive time windows.
        
        Args:
            symbol: Stock symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe identifier (e.g., '1d', '1h', '15')
            center_timestamp: Central timestamp point
            n_before: Number of records to fetch before center
            n_after: Number of records to fetch after center
            exchange: Optional exchange identifier
        
        Returns:
            SQL query string
        
        Raises:
            QueryValidationError: If generated query fails validation
            ValueError: If n_before or n_after are negative
        
        Example:
            >>> from datetime import datetime, timezone
            >>> builder = QueryBuilder('project.dataset.table')
            >>> center = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            >>> query = builder.build_neighborhood_query('BTCUSDT', '15', center, 100, 100)
        """
        # Validate record counts
        if n_before < 0 or n_after < 0:
            raise ValueError(
                f"Record counts must be non-negative: n_before={n_before}, n_after={n_after}"
            )
        
        # Calculate adaptive windows
        window_before_days = calculate_adaptive_window(timeframe, n_before)
        window_after_days = calculate_adaptive_window(timeframe, n_after)
        
        # Build exchange clause
        exchange_clause = build_exchange_clause(exchange)
        
        # Format center timestamp
        center_ts = format_timestamp_for_bigquery(center_timestamp)
        
        # Construct query with UNION ALL strategy
        # This ensures we get exactly N records before, the center, and N records after
        query = f"""
(
  -- {n_before} records BEFORE center timestamp
  SELECT
      timestamp,
      open,
      high,
      low,
      close,
      volume
  FROM
      `{self.table_fqn}`
  WHERE
      symbol = '{symbol}'
      AND timeframe = '{timeframe}'
      AND timestamp < TIMESTAMP '{center_ts}'
      AND timestamp >= TIMESTAMP_SUB(TIMESTAMP '{center_ts}', INTERVAL {window_before_days} DAY)
      {exchange_clause}
  ORDER BY
      timestamp DESC
  LIMIT {n_before}
)
UNION ALL
(
  -- Center record
  SELECT
      timestamp,
      open,
      high,
      low,
      close,
      volume
  FROM
      `{self.table_fqn}`
  WHERE
      symbol = '{symbol}'
      AND timeframe = '{timeframe}'
      AND timestamp = TIMESTAMP '{center_ts}'
      {exchange_clause}
  LIMIT 1
)
UNION ALL
(
  -- {n_after} records AFTER center timestamp
  SELECT
      timestamp,
      open,
      high,
      low,
      close,
      volume
  FROM
      `{self.table_fqn}`
  WHERE
      symbol = '{symbol}'
      AND timeframe = '{timeframe}'
      AND timestamp > TIMESTAMP '{center_ts}'
      AND timestamp <= TIMESTAMP_ADD(TIMESTAMP '{center_ts}', INTERVAL {window_after_days} DAY)
      {exchange_clause}
  ORDER BY
      timestamp ASC
  LIMIT {n_after}
)
ORDER BY
    timestamp ASC
""".strip()
        
        # Validate query before returning
        # Note: UNION ALL query has multiple timestamp predicates, validator will find them
        self.validator.validate_query(query, symbol, timeframe, exchange)
        
        return query

