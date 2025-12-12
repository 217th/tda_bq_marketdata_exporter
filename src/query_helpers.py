"""
Query helper utilities for BigQuery SQL construction.

Provides reusable functions for adaptive window calculation,
exchange clause generation, and other query utilities.
"""

from datetime import datetime, timedelta
from typing import Optional


# Timeframe to records-per-day mapping
# Used for adaptive window calculation
RECORDS_PER_DAY = {
    '1M': 1 / 30,    # 1 candle per 30 days
    '1w': 1 / 7,     # 1 candle per 7 days
    '1d': 1,         # 1 candle per day
    '4h': 6,         # 6 candles per day
    '1h': 24,        # 24 candles per day
    '15': 96,        # 96 candles per day (15-minute)
    '5': 288,        # 288 candles per day (5-minute)
    '1': 1440,       # 1440 candles per day (1-minute)
}


def calculate_adaptive_window(timeframe: str, records_needed: int) -> int:
    """Calculate adaptive time window in days based on timeframe and record count.
    
    For NEIGHBORHOOD mode queries, this determines how many days before/after
    the center timestamp to query to ensure we fetch the required number of candles
    while satisfying BigQuery partition predicates.
    
    Args:
        timeframe: Timeframe identifier ('1M', '1w', '1d', '4h', '1h', '15', '5', '1')
        records_needed: Number of records to fetch (e.g., n_before or n_after)
    
    Returns:
        Number of days for the query window (minimum 1, maximum 5475 = 15 years)
    
    Example:
        >>> calculate_adaptive_window('15', 100)
        2  # For 100 15-minute candles, query ~2 days (with buffer)
        
        >>> calculate_adaptive_window('1M', 3)
        108  # For 3 monthly candles, query ~108 days (with buffer)
    """
    records_per_day = RECORDS_PER_DAY.get(timeframe, 1)
    
    # Calculate days needed with 20% buffer
    days_needed = int((records_needed / records_per_day) * 1.2)
    
    # Clamp to reasonable range: 1 day to 15 years (5475 days)
    return max(1, min(5475, days_needed))


def build_exchange_clause(exchange: Optional[str]) -> str:
    """Build SQL WHERE clause for exchange filtering.
    
    Args:
        exchange: Exchange identifier (e.g., 'BINANCE'), or None
    
    Returns:
        SQL clause string for exchange filter (empty if exchange not specified)
    
    Example:
        >>> build_exchange_clause('BINANCE')
        "AND exchange = 'BINANCE'"
        
        >>> build_exchange_clause(None)
        ""
    """
    if exchange:
        # Escape single quotes in exchange name
        escaped_exchange = exchange.replace("'", "''")
        return f"AND exchange = '{escaped_exchange}'"
    return ""


def format_timestamp_for_bigquery(dt: datetime) -> str:
    """Format datetime for BigQuery TIMESTAMP literal.
    
    Args:
        dt: Datetime object (should be timezone-aware)
    
    Returns:
        BigQuery-compatible timestamp string
    
    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        >>> format_timestamp_for_bigquery(dt)
        '2024-01-01 12:00:00+00:00'
    """
    return dt.isoformat(sep=' ')


def calculate_default_time_range(years: int = 15) -> tuple[datetime, datetime]:
    """Calculate default time range for ALL mode queries.
    
    Args:
        years: Number of years of history (default: 15)
    
    Returns:
        Tuple of (start_timestamp, end_timestamp)
    
    Example:
        >>> start, end = calculate_default_time_range(15)
        >>> # Returns (15 years ago, now)
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=years * 365)
    return start_time, end_time


def validate_symbol_format(symbol: str) -> bool:
    """Validate symbol format (alphanumeric, typically like BTCUSDT).
    
    Args:
        symbol: Symbol identifier
    
    Returns:
        True if valid format, False otherwise
    
    Example:
        >>> validate_symbol_format('BTCUSDT')
        True
        
        >>> validate_symbol_format('BTC-USDT')
        False
        
        >>> validate_symbol_format('BTC USDT')
        False
    """
    return symbol.isalnum() and symbol.isupper()


def validate_timeframe(timeframe: str) -> bool:
    """Validate timeframe is one of the supported values.
    
    Args:
        timeframe: Timeframe identifier
    
    Returns:
        True if valid, False otherwise
    
    Example:
        >>> validate_timeframe('1d')
        True
        
        >>> validate_timeframe('30m')
        False
    """
    return timeframe in RECORDS_PER_DAY

