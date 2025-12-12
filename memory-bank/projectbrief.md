# Project Brief: BigQuery Stock Quotes Extractor

## Project Overview
Python 3.13 script for extracting historical stock market quotes from Google BigQuery database.

## Execution Environment
- **Runtime**: Local execution
- **Python Version**: 3.13
- **Database**: Google BigQuery

## Data Schema
Table contains the following columns:
- `timestamp` (TIMESTAMP) - Time of the quote
- `exchange` (STRING) - Exchange identifier
- `symbol` (STRING) - Stock symbol
- `timeframe` (STRING) - Time interval
- `open` (FLOAT) - Opening price
- `high` (FLOAT) - Highest price
- `low` (FLOAT) - Lowest price
- `close` (FLOAT) - Closing price
- `volume` (FLOAT) - Trading volume
- `ingested_at` (TIMESTAMP) - Data ingestion timestamp

## Configuration Requirements
Environment variables (`.env` file):
- Dataset name
- Table name
- Path to Google Cloud JSON key file

## Input Parameters
### Required:
- `symbol` - Stock symbol in format like BTCUSDT, ETHUSDT, etc. (mandatory)
- `timeframe` - Values: '1M', '1w', '1d', '4h', '1h', '15', '5', '1' (mandatory)
- **Timestamp condition** - MANDATORY due to table partitioning by timestamp field

### Optional:
- `exchange` - Exchange identifier (if not provided and multiple exchanges found, use first)

### Time Interval Options (one required):
1. All records for the symbol (last 15 years of historical data)
2. Range: from...to... (explicit timestamp range)
3. Neighborhood: n records before timestamp, n records after timestamp

**CRITICAL**: Due to BigQuery table partitioning by `timestamp`, every query MUST include a timestamp condition to avoid scanning the entire table. The "all records" option uses a 15-year window.

## API Resilience
Backoff strategy for BigQuery requests:
- `backoff_base`: 1.0
- `backoff_factor`: 2.0
- `backoff_max`: 32.0
- `backoff_attempts`: 5

## Output Format
JSON file saved to project folder with the following structure:
```json
{
  "candle_fields": [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume"
  ],
  "data": [
    {
      "date": "2024-01-01T00:00:00Z",
      "open": 43000.0,
      "high": 43500.0,
      "low": 42800.0,
      "close": 43200.0,
      "volume": 1234.56
    }
  ]
}
```

Output filename pattern: `{symbol}_{timeframe}_{timestamp}.json`

## Project Goals
Create a robust, maintainable Python script that:
1. Retrieves configuration from environment variables
2. Connects to Google BigQuery with proper authentication
3. Constructs dynamic queries based on input parameters (respecting partition requirements)
4. Handles API failures with exponential backoff
5. Saves data to JSON file in project folder
6. Implements structured logging (similar to existing project patterns, without Loki initially)

