"""
Unit tests for query builder modules.
"""

from datetime import datetime, timezone, timedelta

import pytest

from src.query_helpers import (
    calculate_adaptive_window,
    build_exchange_clause,
    format_timestamp_for_bigquery,
    calculate_default_time_range,
    validate_symbol_format,
    validate_timeframe,
    RECORDS_PER_DAY,
)
from src.query_validator import QueryValidator, QueryValidationError
from src.query_builder import QueryBuilder


class TestQueryHelpers:
    """Test query helper functions."""
    
    def test_calculate_adaptive_window_minute(self):
        """Test adaptive window for 1-minute timeframe."""
        # 100 1-minute candles = ~100/1440 days ≈ 0.07 days → min 1 day
        assert calculate_adaptive_window('1', 100) == 1
        
        # 2000 1-minute candles ≈ 1.39 days → with buffer ≈ 2 days
        assert calculate_adaptive_window('1', 2000) >= 1
    
    def test_calculate_adaptive_window_15min(self):
        """Test adaptive window for 15-minute timeframe."""
        # 100 15-minute candles = ~100/96 days ≈ 2 days (with buffer)
        assert calculate_adaptive_window('15', 100) >= 1
    
    def test_calculate_adaptive_window_hourly(self):
        """Test adaptive window for hourly timeframe."""
        # 100 hourly candles = ~100/24 days ≈ 5 days (with buffer)
        assert calculate_adaptive_window('1h', 100) >= 4
    
    def test_calculate_adaptive_window_daily(self):
        """Test adaptive window for daily timeframe."""
        # 30 daily candles = 30 days → with buffer ≈ 36 days
        assert calculate_adaptive_window('1d', 30) >= 30
    
    def test_calculate_adaptive_window_monthly(self):
        """Test adaptive window for monthly timeframe."""
        # 3 monthly candles = ~90 days → with buffer ≈ 108 days
        window = calculate_adaptive_window('1M', 3)
        assert window >= 90  # Should be around 108 days
    
    def test_calculate_adaptive_window_max_limit(self):
        """Test adaptive window respects maximum limit (15 years)."""
        # Requesting huge number of candles should cap at 5475 days
        assert calculate_adaptive_window('1d', 10000) == 5475
    
    def test_build_exchange_clause_with_exchange(self):
        """Test exchange clause generation with exchange."""
        clause = build_exchange_clause('BINANCE')
        assert "AND exchange = 'BINANCE'" == clause
    
    def test_build_exchange_clause_without_exchange(self):
        """Test exchange clause generation without exchange."""
        clause = build_exchange_clause(None)
        assert clause == ""
    
    def test_build_exchange_clause_escapes_quotes(self):
        """Test exchange clause escapes single quotes."""
        clause = build_exchange_clause("TEST'EXCHANGE")
        assert "AND exchange = 'TEST''EXCHANGE'" == clause
    
    def test_format_timestamp_for_bigquery(self):
        """Test timestamp formatting for BigQuery."""
        dt = datetime(2024, 6, 15, 12, 30, 45, tzinfo=timezone.utc)
        formatted = format_timestamp_for_bigquery(dt)
        assert '2024-06-15' in formatted
        assert '12:30:45' in formatted
    
    def test_calculate_default_time_range(self):
        """Test default time range calculation."""
        start, end = calculate_default_time_range(years=15)
        
        # Start should be ~15 years ago
        expected_start = datetime.utcnow() - timedelta(days=15 * 365)
        assert abs((start - expected_start).days) <= 1
        
        # End should be close to now
        assert abs((end - datetime.utcnow()).total_seconds()) < 60
    
    def test_validate_symbol_format_valid(self):
        """Test symbol validation with valid symbols."""
        assert validate_symbol_format('BTCUSDT') is True
        assert validate_symbol_format('ETHUSDT') is True
        assert validate_symbol_format('BTC') is True
    
    def test_validate_symbol_format_invalid(self):
        """Test symbol validation with invalid symbols."""
        assert validate_symbol_format('BTC-USDT') is False
        assert validate_symbol_format('btcusdt') is False  # lowercase
        assert validate_symbol_format('BTC USDT') is False
        assert validate_symbol_format('BTC_USDT') is False
    
    def test_validate_timeframe_valid(self):
        """Test timeframe validation with valid timeframes."""
        for tf in RECORDS_PER_DAY.keys():
            assert validate_timeframe(tf) is True
    
    def test_validate_timeframe_invalid(self):
        """Test timeframe validation with invalid timeframes."""
        assert validate_timeframe('30m') is False
        assert validate_timeframe('2h') is False
        assert validate_timeframe('invalid') is False


class TestQueryValidator:
    """Test query validator."""
    
    def test_validate_has_timestamp_predicate_gte(self):
        """Test validation passes with >= predicate."""
        sql = "SELECT * FROM table WHERE timestamp >= '2024-01-01'"
        QueryValidator.validate_has_timestamp_predicate(sql)
        # Should not raise
    
    def test_validate_has_timestamp_predicate_lte(self):
        """Test validation passes with <= predicate."""
        sql = "SELECT * FROM table WHERE timestamp <= '2024-12-31'"
        QueryValidator.validate_has_timestamp_predicate(sql)
        # Should not raise
    
    def test_validate_has_timestamp_predicate_between(self):
        """Test validation passes with BETWEEN predicate."""
        sql = "SELECT * FROM table WHERE timestamp BETWEEN '2024-01-01' AND '2024-12-31'"
        QueryValidator.validate_has_timestamp_predicate(sql)
        # Should not raise
    
    def test_validate_has_timestamp_predicate_missing(self):
        """Test validation fails without timestamp predicate."""
        sql = "SELECT * FROM table WHERE symbol = 'BTCUSDT'"
        with pytest.raises(QueryValidationError, match="Missing timestamp predicate"):
            QueryValidator.validate_has_timestamp_predicate(sql)
    
    def test_validate_has_required_filters_all_present(self):
        """Test validation passes when all filters present."""
        sql = """
        SELECT * FROM table
        WHERE symbol = 'BTCUSDT'
        AND timeframe = '1d'
        AND exchange = 'BINANCE'
        AND timestamp >= '2024-01-01'
        """
        QueryValidator.validate_has_required_filters(sql, 'BTCUSDT', '1d', 'BINANCE')
        # Should not raise
    
    def test_validate_has_required_filters_missing_symbol(self):
        """Test validation fails when symbol filter missing."""
        sql = "SELECT * FROM table WHERE timeframe = '1d'"
        with pytest.raises(QueryValidationError, match="Missing symbol filter"):
            QueryValidator.validate_has_required_filters(sql, 'BTCUSDT', '1d')
    
    def test_validate_has_required_filters_missing_timeframe(self):
        """Test validation fails when timeframe filter missing."""
        sql = "SELECT * FROM table WHERE symbol = 'BTCUSDT'"
        with pytest.raises(QueryValidationError, match="Missing timeframe filter"):
            QueryValidator.validate_has_required_filters(sql, 'BTCUSDT', '1d')
    
    def test_validate_query_complete(self):
        """Test complete query validation."""
        sql = """
        SELECT * FROM table
        WHERE symbol = 'BTCUSDT'
        AND timeframe = '1d'
        AND timestamp >= '2024-01-01'
        AND timestamp <= '2024-12-31'
        """
        QueryValidator.validate_query(sql, 'BTCUSDT', '1d')
        # Should not raise


class TestQueryBuilder:
    """Test query builder."""
    
    @pytest.fixture
    def builder(self):
        """Create query builder instance."""
        return QueryBuilder('test-project.test_dataset.test_table')
    
    def test_build_all_query_structure(self, builder):
        """Test ALL query structure and validation."""
        query = builder.build_all_query('BTCUSDT', '1d')
        
        # Check query contains required elements
        assert 'test-project.test_dataset.test_table' in query
        assert "symbol = 'BTCUSDT'" in query
        assert "timeframe = '1d'" in query
        assert 'timestamp >=' in query
        assert 'timestamp <=' in query
        assert 'ORDER BY' in query
        assert 'timestamp ASC' in query
    
    def test_build_all_query_with_exchange(self, builder):
        """Test ALL query with exchange filter."""
        query = builder.build_all_query('BTCUSDT', '1d', exchange='BINANCE')
        
        assert "exchange = 'BINANCE'" in query
    
    def test_build_range_query_structure(self, builder):
        """Test RANGE query structure and validation."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)
        
        query = builder.build_range_query('ETHUSDT', '1h', start, end)
        
        # Check query contains required elements
        assert 'test-project.test_dataset.test_table' in query
        assert "symbol = 'ETHUSDT'" in query
        assert "timeframe = '1h'" in query
        assert 'timestamp >=' in query
        assert 'timestamp <=' in query
        assert '2024-01-01' in query
        assert '2024-12-31' in query
    
    def test_build_range_query_invalid_range(self, builder):
        """Test RANGE query fails with invalid time range."""
        start = datetime(2024, 12, 31, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, tzinfo=timezone.utc)
        
        with pytest.raises(ValueError, match="Invalid time range"):
            builder.build_range_query('BTCUSDT', '1d', start, end)
    
    def test_build_neighborhood_query_structure(self, builder):
        """Test NEIGHBORHOOD query structure and validation."""
        center = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        query = builder.build_neighborhood_query('BTCUSDT', '15', center, 100, 100)
        
        # Check query contains required elements
        assert 'test-project.test_dataset.test_table' in query
        assert "symbol = 'BTCUSDT'" in query
        assert "timeframe = '15'" in query
        assert 'UNION ALL' in query
        assert 'LIMIT 100' in query
        assert '2024-06-15' in query
        
        # Check for before/after comments
        assert 'BEFORE' in query
        assert 'AFTER' in query
    
    def test_build_neighborhood_query_negative_counts(self, builder):
        """Test NEIGHBORHOOD query fails with negative record counts."""
        center = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        with pytest.raises(ValueError, match="Record counts must be non-negative"):
            builder.build_neighborhood_query('BTCUSDT', '15', center, -10, 100)
    
    def test_build_neighborhood_query_adaptive_window(self, builder):
        """Test NEIGHBORHOOD query uses adaptive windows."""
        center = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        # For monthly timeframe with 3 records, should have large window
        query = builder.build_neighborhood_query('BTCUSDT', '1M', center, 3, 3)
        
        # Should include INTERVAL with days (at least 90 days for 3 monthly candles)
        assert 'INTERVAL' in query
        assert 'DAY' in query

