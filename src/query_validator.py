"""
Query validator for BigQuery SQL queries.

Enforces critical requirement: all queries MUST include timestamp predicates
because the BigQuery table is partitioned by timestamp field.
"""

import re
from typing import Optional


class QueryValidationError(Exception):
    """Raised when a query fails validation."""
    pass


class QueryValidator:
    """Validates BigQuery SQL queries for required predicates."""
    
    @staticmethod
    def validate_has_timestamp_predicate(sql: str) -> None:
        """Validate that SQL query includes timestamp predicate.
        
        This is CRITICAL because the BigQuery table is partitioned by timestamp.
        Queries without timestamp predicates will scan the entire table,
        causing performance issues and increased costs.
        
        Args:
            sql: SQL query string to validate
        
        Raises:
            QueryValidationError: If query lacks timestamp predicate
        
        Example:
            >>> sql = "SELECT * FROM table WHERE timestamp >= '2024-01-01'"
            >>> QueryValidator.validate_has_timestamp_predicate(sql)
            # Passes validation
            
            >>> sql = "SELECT * FROM table WHERE symbol = 'BTCUSDT'"
            >>> QueryValidator.validate_has_timestamp_predicate(sql)
            # Raises QueryValidationError
        """
        # Normalize SQL for pattern matching (lowercase, collapse whitespace)
        normalized_sql = ' '.join(sql.lower().split())
        
        # Check for timestamp predicates
        # Patterns to match:
        # - timestamp >= ...
        # - timestamp <= ...
        # - timestamp BETWEEN ... AND ...
        # - timestamp > ...
        # - timestamp < ...
        # - timestamp = ...
        timestamp_patterns = [
            r'\btimestamp\s*>=',
            r'\btimestamp\s*<=',
            r'\btimestamp\s*>',
            r'\btimestamp\s*<',
            r'\btimestamp\s*=',
            r'\btimestamp\s+between\b',
        ]
        
        has_timestamp_predicate = any(
            re.search(pattern, normalized_sql)
            for pattern in timestamp_patterns
        )
        
        if not has_timestamp_predicate:
            raise QueryValidationError(
                "Query validation failed: Missing timestamp predicate. "
                "All queries MUST include timestamp conditions because table is partitioned by timestamp. "
                "Example: WHERE timestamp >= '2024-01-01' AND timestamp < '2024-12-31'"
            )
    
    @staticmethod
    def validate_has_required_filters(
        sql: str,
        symbol: str,
        timeframe: str,
        exchange: Optional[str] = None
    ) -> None:
        """Validate that SQL query includes all required filter predicates.
        
        Args:
            sql: SQL query string to validate
            symbol: Expected symbol filter
            timeframe: Expected timeframe filter
            exchange: Expected exchange filter (optional)
        
        Raises:
            QueryValidationError: If query lacks required filters
        """
        normalized_sql = ' '.join(sql.lower().split())
        
        # Check for symbol
        if f"symbol = '{symbol.lower()}'" not in normalized_sql:
            raise QueryValidationError(
                f"Query validation failed: Missing symbol filter for '{symbol}'"
            )
        
        # Check for timeframe
        if f"timeframe = '{timeframe.lower()}'" not in normalized_sql:
            raise QueryValidationError(
                f"Query validation failed: Missing timeframe filter for '{timeframe}'"
            )
        
        # Check for exchange if specified
        if exchange:
            if f"exchange = '{exchange.lower()}'" not in normalized_sql:
                raise QueryValidationError(
                    f"Query validation failed: Missing exchange filter for '{exchange}'"
                )
    
    @staticmethod
    def validate_query(
        sql: str,
        symbol: str,
        timeframe: str,
        exchange: Optional[str] = None
    ) -> None:
        """Perform all query validations.
        
        This is the main validation method that should be called before
        executing any query.
        
        Args:
            sql: SQL query string to validate
            symbol: Expected symbol filter
            timeframe: Expected timeframe filter
            exchange: Expected exchange filter (optional)
        
        Raises:
            QueryValidationError: If any validation fails
        """
        # Critical: validate timestamp predicate
        QueryValidator.validate_has_timestamp_predicate(sql)
        
        # Validate required filters
        QueryValidator.validate_has_required_filters(sql, symbol, timeframe, exchange)

