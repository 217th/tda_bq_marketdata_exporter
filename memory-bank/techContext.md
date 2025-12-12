# Technical Context

## Technology Stack

### Language
- **Python 3.13**
  - Modern Python features
  - Type hints support
  - Enhanced error messages

### Cloud Platform
- **Google Cloud Platform (GCP)**
  - BigQuery for data warehouse
  - Service account authentication
  - JSON key-based credentials

### Key Libraries (To be determined in CREATIVE phase)
- `google-cloud-bigquery` - Official BigQuery client
- `python-dotenv` - Environment configuration
- Backoff/retry library (TBD)

## Data Architecture

### BigQuery Table Schema
```sql
CREATE TABLE dataset.table (
  timestamp TIMESTAMP,      -- PARTITION FIELD (queries MUST filter on this)
  exchange STRING,
  symbol STRING,            -- Format: BTCUSDT, ETHUSDT, etc.
  timeframe STRING,
  open FLOAT64,
  high FLOAT64,
  low FLOAT64,
  close FLOAT64,
  volume FLOAT64,
  ingested_at TIMESTAMP
)
PARTITION BY DATE(timestamp)  -- Table is partitioned by timestamp
```

**CRITICAL REQUIREMENT**: Table is partitioned by `timestamp` field. All queries MUST include a predicate on `timestamp` to avoid full table scans and ensure efficient query execution.

## Authentication Model
- Service Account JSON key file
- Path specified in environment variable
- Scope: BigQuery read access

## Query Patterns

### Base Query Structure (with REQUIRED timestamp predicate)
```sql
SELECT 
  timestamp,
  open,
  high,
  low,
  close,
  volume
FROM `{project}.{dataset}.{table}`
WHERE symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp >= @start_time      -- REQUIRED for partition pruning
  AND timestamp <= @end_time        -- REQUIRED for partition pruning
  [AND exchange = @exchange]        -- Optional
ORDER BY timestamp ASC
```

### Query Variations:
1. **All records**: Use full historical range (15 years)
   ```sql
   AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5475 DAY)  -- 15 лет
   AND timestamp <= CURRENT_TIMESTAMP()
   ```

2. **Range**: Explicit from/to timestamps
   ```sql
   AND timestamp >= @from_timestamp
   AND timestamp <= @to_timestamp
   ```

3. **Neighborhood**: Record-based window (exact N records before/after)
   ```sql
   -- Query uses ADAPTIVE window calculated based on timeframe and record count
   -- Examples: 
   --   1M timeframe, 3 records: window = ~108 days (3.6 months)
   --   1d timeframe, 100 records: window = ~120 days
   --   1h timeframe, 100 records: window = ~5 days
   
   -- Query for N records BEFORE center point
   (SELECT timestamp, open, high, low, close, volume
    FROM `{project}.{dataset}.{table}`
    WHERE symbol = @symbol
      AND timeframe = @timeframe
      AND timestamp < @center_timestamp
      AND timestamp >= TIMESTAMP_SUB(@center_timestamp, INTERVAL @adaptive_window_days DAY)
    ORDER BY timestamp DESC
    LIMIT @n_before)
   
   UNION ALL
   
   -- Query for center point (optional)
   (SELECT timestamp, open, high, low, close, volume
    FROM `{project}.{dataset}.{table}`
    WHERE symbol = @symbol
      AND timeframe = @timeframe
      AND timestamp = @center_timestamp
    LIMIT 1)
   
   UNION ALL
   
   -- Query for N records AFTER center point
   (SELECT timestamp, open, high, low, close, volume
    FROM `{project}.{dataset}.{table}`
    WHERE symbol = @symbol
      AND timeframe = @timeframe
      AND timestamp > @center_timestamp
      AND timestamp <= TIMESTAMP_ADD(@center_timestamp, INTERVAL @adaptive_window_days DAY)
    ORDER BY timestamp ASC
    LIMIT @n_after)
   
   ORDER BY timestamp ASC
   ```
   
   Note: Window is calculated adaptively:
   - Formula: `days = (records_needed / records_per_day) * 1.2`
   - records_per_day varies by timeframe: 1M=1/30, 1w=1/7, 1d=1, 4h=6, 1h=24, etc.
   - 20% buffer accounts for data gaps and non-trading days
   - Maximum window capped at 5475 days (15 years)

**PARTITION REQUIREMENT**: Every query variation MUST include timestamp predicates to satisfy partition pruning requirements.

## Error Handling Strategy

### Backoff Configuration
```python
Base delay: 1.0 seconds
Multiplier: 2.0 (exponential)
Maximum delay: 32.0 seconds
Max attempts: 5
```

### Retry-able Errors:
- Network timeouts
- Rate limiting (429)
- Temporary server errors (5xx)

### Non-retry-able Errors:
- Authentication failures (401, 403)
- Invalid query syntax (400)
- Resource not found (404)

## Development Environment
- Local execution
- Requires `.env` file for configuration
- No containerization (yet)

## Logging Architecture

Based on existing project pattern (see temp/logging_util.py):

### Logging Approach:
- Structured logging with JSON format
- Service name and environment from config
- Console output (StreamHandler)
- Loki integration deferred to future stages

### Logger Configuration:
```python
def build_logger(service_name: str, environment: str, level: str = "INFO"):
    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    
    formatter = logging.Formatter("%(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    return logger

def log_struct(logger, labels, fields):
    record = {**fields, **{f"label_{k}": v for k, v in labels.items()}}
    logger.info(json.dumps(record))
```

### Log Message Structure:
```json
{
  "message": "Query executed successfully",
  "label_service_name": "bigquery-extractor",
  "label_environment": "dev",
  "symbol": "BTCUSDT",
  "timeframe": "1d",
  "rows_returned": 365,
  "query_duration_ms": 1234
}
```

## Output Format
- JSON file saved to project folder
- UTF-8 encoding
- Pretty-printed (indent=2)
- Filename: `{symbol}_{timeframe}_{start_timestamp}.json`

## Performance Considerations
- Query result pagination (for large datasets)
- Connection pooling (if needed)
- Query timeout settings

## Security Considerations
- Credentials never hardcoded
- Environment variables for sensitive data
- Service account with minimal required permissions
- Credentials file outside version control

