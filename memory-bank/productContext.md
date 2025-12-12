# Product Context

## Purpose
Extract historical stock market quote data from Google BigQuery for analysis and processing.

## Target Users
- Data analysts
- Algorithmic traders
- Financial researchers
- System integrators

## Use Cases

### Use Case 1: Full Historical Data Export
**Scenario**: User needs all available data for a symbol
**Input**: `--symbol BTCUSDT --timeframe 1d --all`
**Behavior**: Queries last 15 years (5475 days) - entire historical range
**Output**: JSON file `BTCUSDT_1d_20091211.json` saved to project folder
**Note**: Timestamp predicate satisfied with 15-year window

### Use Case 2: Date Range Query
**Scenario**: User needs data for specific time period
**Input**: `--symbol ETHUSDT --timeframe 1h --from 2024-01-01 --to 2024-01-31`
**Output**: JSON file `ETHUSDT_1h_20240101.json` with January 2024 data

### Use Case 3: Neighborhood Query (15-minute timeframe)
**Scenario**: User needs context around a specific event
**Input**: `--symbol BTCUSDT --timeframe 15 --around 2024-01-15T10:30:00 --before 100 --after 100`
**Output**: JSON file with exactly 201 candles (100 before center, center candle, 100 after center)
**Query Strategy**: 
- Calculates adaptive window: 100 candles × 15min = ~1 day window (with buffer)
- Uses UNION ALL of three queries (before/center/after)
- Each query uses calculated window to satisfy partition requirement
- LIMIT ensures exact record count
- Final ORDER BY timestamp ensures chronological order

### Use Case 3a: Neighborhood Query (1-month timeframe)
**Scenario**: User needs context around monthly price action
**Input**: `--symbol BTCUSDT --timeframe 1M --around 2024-06-01T00:00:00 --before 3 --after 3`
**Output**: JSON file with exactly 7 candles (3 months before, center month, 3 months after)
**Query Strategy**:
- Calculates adaptive window: 3 candles ÷ (1/30 candles/day) × 1.2 = ~108 days window
- Window is large enough to capture 3+ monthly candles despite the sparse data
- Example: if center is June 2024, window extends from ~March to ~September

### Use Case 4: Multi-Exchange Symbol
**Scenario**: Symbol exists on multiple exchanges, user doesn't specify
**Input**: `--symbol BTCUSDT --timeframe 1d --all`
**Behavior**: Use first exchange found (deterministic order)

### Use Case 5: Custom Output Location
**Scenario**: User wants to save output to specific directory
**Input**: `--symbol BTCUSDT --timeframe 1d --all --output /path/to/output`
**Output**: File saved to specified directory

## Success Metrics
- Correct data retrieval (100% accuracy)
- Successful authentication
- Graceful error handling
- Reasonable query performance
- Clear error messages

## Integration Points
- Input: Command-line interface
- Output: JSON file saved to project folder (configurable location)
- Configuration: .env file
- Authentication: GCP service account
- Logging: Structured JSON logs to stdout

## Constraints
- Local execution only (no server component)
- Read-only access to BigQuery
- Must handle large result sets efficiently
- Must respect BigQuery quotas and rate limits

## Future Enhancements (Out of Scope)
- Multiple symbols in one query
- Real-time data streaming
- Built-in data caching
- Output format options (CSV, Parquet)
- Database export functionality

