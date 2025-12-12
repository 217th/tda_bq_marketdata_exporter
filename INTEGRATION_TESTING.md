# Integration Testing Guide

This guide explains how to test the BigQuery Stock Quotes Extractor with real BigQuery data.

## Prerequisites

1. **Google Cloud Project** with BigQuery enabled
2. **Service Account Key** (JSON file) with BigQuery permissions
3. **BigQuery Table** with stock quotes data (schema documented in `memory-bank/techContext.md`)
4. **.env File** configured with your credentials

## Setup

### 1. Create .env File

Copy the template and fill in your values:

```bash
cp env.example .env
nano .env
```

Required configuration:

```env
GCP_PROJECT_ID=your-project-id
BQ_DATASET=your_dataset_name
BQ_TABLE=your_table_name
GCP_KEY_PATH=/path/to/your/service-account-key.json
SERVICE_NAME=bq-stock-extractor
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### 2. Verify BigQuery Table Schema

Your BigQuery table must have the following schema:

```sql
CREATE TABLE `project.dataset.table` (
    timestamp TIMESTAMP,
    exchange STRING,
    symbol STRING,
    timeframe STRING,
    open FLOAT64,
    high FLOAT64,
    low FLOAT64,
    close FLOAT64,
    volume FLOAT64,
    ingested_at TIMESTAMP
)
PARTITION BY DATE(timestamp);
```

**CRITICAL**: Table must be partitioned by `timestamp` field.

## Integration Tests

### Test 1: ALL Mode (15 Years of Data)

Query all available historical data for a symbol:

```bash
python main.py --symbol BTCUSDT --timeframe 1d --all
```

**Expected Outcome**:
- Query executes successfully
- Returns up to 15 years of daily candles
- Output file: `BTCUSDT_1d_YYYYMMDD_HHMMSS.json`
- Structured logs in JSON format

### Test 2: RANGE Mode (Specific Time Period)

Query data within a specific time range:

```bash
python main.py --symbol ETHUSDT --timeframe 1h \
  --from 2024-01-01T00:00:00Z \
  --to 2024-01-31T23:59:59Z
```

**Expected Outcome**:
- Returns hourly candles for January 2024
- Validates time range (from < to)
- Output file: `ETHUSDT_1h_YYYYMMDD_HHMMSS.json`

### Test 3: NEIGHBORHOOD Mode (Records Around Timestamp)

Query N records before and after a specific timestamp:

```bash
python main.py --symbol BTCUSDT --timeframe 15 \
  --timestamp 2024-06-15T12:00:00Z \
  --n-before 100 \
  --n-after 100
```

**Expected Outcome**:
- Returns exactly 100 15-minute candles before center timestamp
- Returns the center candle
- Returns exactly 100 15-minute candles after center timestamp
- Total records: 201 (100 + 1 + 100)
- Adaptive window calculated based on timeframe

### Test 4: With Exchange Filter

Test with optional exchange parameter:

```bash
python main.py --symbol BTCUSDT --timeframe 1d --all --exchange BINANCE
```

**Expected Outcome**:
- Query includes exchange filter
- Returns data only for specified exchange

### Test 5: Output to Custom Directory

Test custom output directory:

```bash
mkdir -p ./output
python main.py --symbol BTCUSDT --timeframe 1d --all --output ./output
```

**Expected Outcome**:
- Output directory created if doesn't exist
- File saved in `./output/BTCUSDT_1d_YYYYMMDD_HHMMSS.json`

### Test 6: Error Handling - Invalid Symbol Format

Test validation error handling:

```bash
python main.py --symbol btc-usdt --timeframe 1d --all
```

**Expected Outcome**:
- Validation error: "Invalid symbol format"
- Exit code: 1
- Error logged in JSON format

### Test 7: Error Handling - Missing Timestamp Predicate

This should never happen (validator prevents it), but if you manually modify query:

**Expected Outcome**:
- QueryValidationError raised
- Error message: "Missing timestamp predicate"
- Query not executed

### Test 8: Retry Logic - Transient Network Errors

To test retry logic, you can:
1. Temporarily disable network
2. Observe retry attempts in logs
3. Restore network
4. Query should eventually succeed

**Expected Behavior**:
- Up to 5 retry attempts (BACKOFF_ATTEMPTS)
- Exponential backoff delays: 1s, 2s, 4s, 8s, 16s (capped at 32s)
- Retryable errors: ServiceUnavailable, DeadlineExceeded, ResourceExhausted

## Monitoring and Logs

All logs are output in structured JSON format to stdout. Example log entry:

```json
{
  "timestamp": "2024-12-11T10:30:45.123Z",
  "level": "INFO",
  "logger": "bq-stock-extractor",
  "message": "Query completed successfully, 365 rows returned",
  "labels": {
    "service": "bq-stock-extractor",
    "environment": "development",
    "symbol": "BTCUSDT",
    "timeframe": "1d",
    "mode": "ALL"
  },
  "fields": {
    "row_count": 365,
    "bytes_processed": 12345,
    "bytes_billed": 10240
  }
}
```

## Performance Testing

### Test Query Performance

1. **Small Query** (1 day of 15-minute data):
   - Expected: < 5 seconds
   - Records: ~96 candles

2. **Medium Query** (1 month of hourly data):
   - Expected: < 10 seconds
   - Records: ~720 candles

3. **Large Query** (15 years of daily data):
   - Expected: < 30 seconds (depends on table size)
   - Records: ~5475 candles

### Verify Partition Pruning

Check BigQuery logs/console to verify partition pruning is working:
- Query should only scan partitions within the specified time range
- Bytes scanned should be proportional to time range, not full table

## Troubleshooting

### Issue: "Resource not found" Error

**Cause**: Invalid GCP_PROJECT_ID, BQ_DATASET, or BQ_TABLE in .env

**Solution**:
1. Verify project ID in GCP Console
2. Verify dataset and table exist
3. Check spelling in .env file

### Issue: "Permission denied" Error

**Cause**: Service account lacks BigQuery permissions

**Solution**:
1. Grant `BigQuery Data Viewer` role to service account
2. Grant `BigQuery Job User` role to service account
3. Verify key file path is correct

### Issue: "No data found" Warning

**Cause**: Query returned zero records

**Solution**:
1. Verify symbol exists in table
2. Check timeframe value
3. Verify data exists for the requested time range
4. Try querying with fewer filters (e.g., without exchange)

### Issue: Query Too Slow

**Cause**: Not using partition pruning, or querying unindexed columns

**Solution**:
1. Verify table is partitioned by timestamp
2. Ensure all queries include timestamp predicates (automatically enforced by QueryValidator)
3. Consider clustering on symbol and timeframe fields

## Exit Codes

- `0`: Success (or no data found, which is not an error)
- `1`: Configuration or validation error
- `2`: Authentication error
- `3`: Query execution or network error
- `4`: Filesystem error

## Next Steps

After successful integration testing:
1. Run with production credentials (if different from dev)
2. Set up monitoring/alerting for errors
3. Integrate with Loki for log aggregation (future enhancement)
4. Consider adding more query modes or filters as needed

