# Integration Testing Guide

This guide explains how to test the BigQuery Stock Quotes Extractor with real BigQuery data and Google Cloud Storage.

## Prerequisites

### Required
1. **Google Cloud Project** with BigQuery enabled
2. **BigQuery Service Account Key** (JSON file) with BigQuery permissions
3. **BigQuery Table** with stock quotes data (schema documented in `memory-bank/techContext.md`)
4. **.env File** configured with your credentials

### Optional (for GCS testing)
5. **Google Cloud Storage Bucket** with public access configured
6. **GCS Service Account Key** (JSON file, separate from BigQuery) with Storage permissions

## Setup

### 1. Create .env File

Copy the template and fill in your values:

```bash
cp env.example .env
nano .env
```

Required configuration (BigQuery):

```env
# BigQuery Configuration (Required)
GCP_PROJECT_ID=your-project-id
BQ_DATASET=your_dataset_name
BQ_TABLE=your_table_name
GCP_KEY_PATH=/path/to/bigquery-service-account-key.json

# Application Configuration
SERVICE_NAME=bq-stock-extractor
ENVIRONMENT=development
LOG_LEVEL=INFO

# Google Cloud Storage Configuration (Optional)
GCS_BUCKET_NAME=your-bucket-name
GCS_SERVICE_ACCOUNT_KEY=/path/to/gcs-service-account-key.json
```

**Notes**:
- If `GCS_BUCKET_NAME` and `GCS_SERVICE_ACCOUNT_KEY` are configured, output defaults to GCS
- If GCS not configured, output defaults to local filesystem
- Use `--output` flag to force local filesystem regardless of GCS configuration

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

### 3. Configure GCS Bucket (Optional)

If testing GCS functionality:

1. **Create bucket**:
   ```bash
   gsutil mb gs://your-bucket-name
   ```

2. **Grant public read access**:
   ```bash
   gsutil iam ch allUsers:objectViewer gs://your-bucket-name
   ```

3. **Create service account** with roles:
   - `Storage Object Creator`
   - `Storage Object Viewer`

4. **Download JSON key** and update `.env` with path

## Integration Tests

### Output Modes Overview

The system supports two output modes:

1. **GCS Mode** (Default if configured):
   - Uploads JSON to Google Cloud Storage
   - Returns public download URL
   - Filename: `{request_id}.json`

2. **Local Mode** (With `--output` flag or GCS not configured):
   - Saves JSON to local filesystem
   - Filename: `{request_id}.json`

---

## A. BigQuery Query Tests

### Test A1: ALL Mode (15 Years of Data)

Query all available historical data for a symbol:

```bash
python main.py --symbol BTCUSDT --timeframe 1d --all
```

**Expected Outcome**:
- Query executes successfully
- Returns up to 15 years of daily candles
- **If GCS configured**: File uploaded to GCS, download URL printed
- **If GCS not configured**: File saved locally
- Output filename: `{request_id}.json` (UUID4 format)
- Structured logs in JSON format with request_id

### Test A2: RANGE Mode (Specific Time Period)

Query data within a specific time range:

```bash
python main.py --symbol ETHUSDT --timeframe 1h \
  --from 2024-01-01T00:00:00Z \
  --to 2024-01-31T23:59:59Z
```

**Expected Outcome**:
- Returns hourly candles for January 2024
- Validates time range (from < to)
- Output filename: `{request_id}.json`
- File contains metadata with query_type: "range"

### Test A3: NEIGHBORHOOD Mode (Records Around Timestamp)

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
- File contains metadata with query_type: "neighborhood"

### Test A4: With Exchange Filter

Test with optional exchange parameter:

```bash
python main.py --symbol BTCUSDT --timeframe 1d --all --exchange BINANCE
```

**Expected Outcome**:
- Query includes exchange filter
- Returns data only for specified exchange

---

## B. GCS Output Tests

### Test B1: GCS Upload (Default Behavior)

**Prerequisites**: GCS configured in `.env`

```bash
python main.py --symbol BTCUSDT --timeframe 1d --all
```

**Expected Outcome**:
- ✅ File uploaded to GCS bucket
- ✅ Success message: "Data uploaded to GCS:"
- ✅ Download URL displayed: `https://storage.googleapis.com/bucket-name/{request_id}.json`
- ✅ URL is publicly accessible
- ✅ Temporary local file cleaned up
- ✅ Log includes: "File uploaded to GCS and temp file cleaned up"

**Verification**:
```bash
# Check file exists in bucket
gsutil ls gs://your-bucket-name/

# Download and verify content
curl -o test.json "https://storage.googleapis.com/your-bucket-name/{request_id}.json"
cat test.json | jq '.metadata.request_id'
```

### Test B2: Local Mode with --output Flag

**Prerequisites**: GCS may or may not be configured

```bash
mkdir -p ./test-output
python main.py --symbol BTCUSDT --timeframe 1d --all --output ./test-output
```

**Expected Outcome**:
- ✅ File saved locally: `./test-output/{request_id}.json`
- ✅ Success message: "Data saved locally:"
- ✅ No GCS upload even if configured
- ✅ File path displayed
- ✅ Log includes: "Output file saved locally"

**Verification**:
```bash
ls -lh ./test-output/
cat ./test-output/*.json | jq '.metadata'
```

### Test B3: GCS Graceful Fallback (Invalid Credentials)

**Setup**: Temporarily configure invalid GCS credentials in `.env`

```bash
# In .env, set invalid path:
GCS_SERVICE_ACCOUNT_KEY=/invalid/path/to/key.json

python main.py --symbol BTCUSDT --timeframe 1d --all
```

**Expected Outcome**:
- ⚠️ Warning logged: "GCS unavailable, using local storage only"
- ✅ File saved locally: `./{request_id}.json`
- ✅ Script completes successfully (no crash)
- ✅ Success message: "Data saved locally:"
- ✅ Exit code: 0

**Verification**:
```bash
echo $?  # Should be 0
ls -lh ./*.json
```

### Test B4: GCS Graceful Fallback (Bucket Not Found)

**Setup**: Configure non-existent bucket in `.env`

```bash
# In .env:
GCS_BUCKET_NAME=non-existent-bucket-12345

python main.py --symbol BTCUSDT --timeframe 1d --all
```

**Expected Outcome**:
- ⚠️ Warning logged: "GCS unavailable, using local storage only"
- ✅ File saved locally
- ✅ Script completes successfully

### Test B5: GCS Not Configured

**Setup**: Remove or comment out GCS variables in `.env`

```bash
# In .env, comment out:
# GCS_BUCKET_NAME=...
# GCS_SERVICE_ACCOUNT_KEY=...

python main.py --symbol BTCUSDT --timeframe 1d --all
```

**Expected Outcome**:
- ℹ️ Info log: "GCS not configured, using local storage only"
- ✅ File saved locally: `./{request_id}.json`
- ✅ Normal operation (backward compatible)

### Test B6: Large File Upload to GCS

**Test with large result set**:

```bash
python main.py --symbol BTCUSDT --timeframe 1h --all
```

**Expected Outcome**:
- ✅ Large file (potentially several MB) uploads successfully
- ✅ Reasonable upload time (< 30 seconds for 5MB)
- ✅ Download URL accessible
- ✅ No timeout errors

---

## C. Output Format Tests

### Test C1: Verify Unified Filename Format

**Run multiple queries and check filenames**:

```bash
# Query 1 - GCS mode (if configured)
python main.py --symbol BTCUSDT --timeframe 1d --all

# Query 2 - Local mode
python main.py --symbol ETHUSDT --timeframe 1h --all --output ./output

# Query 3 - Another local
python main.py --symbol BNBUSDT --timeframe 15 --all --output ./output
```

**Expected Outcome**:
- ✅ All filenames follow format: `{request_id}.json`
- ✅ request_id is valid UUID4 (e.g., `550e8400-e29b-41d4-a716-446655440000.json`)
- ✅ No files with old format: `{symbol}_{timeframe}_{timestamp}.json`
- ✅ Each file has unique request_id

### Test C2: Verify Metadata in Output

**Download/open a file and verify structure**:

```json
{
  "metadata": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "request_timestamp": "2025-12-12T10:30:45Z",
    "symbol": "BTCUSDT",
    "timeframe": "1d",
    "query_type": "all",
    "query_parameters": {}
  },
  "data": [
    {
      "date": "2024-01-01T00:00:00Z",
      "open": 42000.5,
      "high": 42500.0,
      "low": 41800.0,
      "close": 42300.0,
      "volume": 1234.56
    }
  ]
}
```

**Verification**:
- ✅ `metadata` object present
- ✅ `metadata.request_id` matches filename
- ✅ `metadata.query_type` correct ("all", "range", or "neighborhood")
- ✅ `data` array present with OHLCV records

---

## D. Error Handling Tests

### Test D1: Invalid Symbol Format

Test validation error handling:

```bash
python main.py --symbol btc-usdt --timeframe 1d --all
```

**Expected Outcome**:
- ❌ Validation error: "Invalid symbol format"
- Exit code: 1
- Error logged in JSON format with request_id

### Test D2: Error Handling - Missing Timestamp Predicate

This should never happen (validator prevents it), but if you manually modify query:

**Expected Outcome**:
- ❌ QueryValidationError raised
- Error message: "Missing timestamp predicate"
- Query not executed

### Test D3: Retry Logic - Transient Network Errors

To test retry logic, you can:
1. Temporarily disable network
2. Observe retry attempts in logs
3. Restore network
4. Query should eventually succeed

**Expected Behavior**:
- Up to 5 retry attempts (BACKOFF_ATTEMPTS)
- Exponential backoff delays: 1s, 2s, 4s, 8s, 16s (capped at 32s)
- Retryable errors: ServiceUnavailable, DeadlineExceeded, ResourceExhausted

### Test D4: GCS Permission Denied

**Setup**: Configure GCS with service account lacking `Storage Object Creator` role

**Expected Outcome**:
- ⚠️ Warning logged: "GCS unavailable, using local storage only"
- ✅ Graceful fallback to local storage
- Exit code: 0 (success)

---

## E. Request Tracking Tests

### Test E1: Request ID Consistency

**Run a query and verify request_id appears everywhere**:

```bash
python main.py --symbol BTCUSDT --timeframe 1d --all 2>&1 | tee output.log
```

**Verification**:
```bash
# Extract request_id from logs
REQUEST_ID=$(cat output.log | grep request_id | jq -r .request_id | head -1)

# Verify it appears in:
# 1. All log messages
cat output.log | jq 'select(.request_id == "'$REQUEST_ID'")'

# 2. Output filename (if local)
ls ./$REQUEST_ID.json

# 3. File metadata
cat ./$REQUEST_ID.json | jq '.metadata.request_id'

# 4. GCS object name (if GCS mode)
# Check in GCS console or via URL
```

**Expected**:
- ✅ Same request_id in all locations
- ✅ Valid UUID4 format
- ✅ Unique for each execution

### Test E2: Multiple Concurrent Requests

**Run multiple requests simultaneously**:

```bash
python main.py --symbol BTCUSDT --timeframe 1d --all --output ./test1 &
python main.py --symbol ETHUSDT --timeframe 1h --all --output ./test2 &
python main.py --symbol BNBUSDT --timeframe 15 --all --output ./test3 &
wait
```

**Expected**:
- ✅ Each request has unique request_id
- ✅ Each creates separate output file
- ✅ No file conflicts
- ✅ Logs distinguishable by request_id

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
- `2`: Authentication error (BigQuery)
- `3`: Query execution or network error
- `4`: Filesystem error (local storage)
- `5`: GCS upload error (retryable) - Falls back to local
- `6`: GCS authentication error - Falls back to local

**Note**: GCS errors (5, 6) trigger graceful fallback and return exit code 0 if local save succeeds.

## F. Complete Integration Test Checklist

Use this checklist for comprehensive testing:

### BigQuery Tests
- [ ] Test A1: ALL mode query
- [ ] Test A2: RANGE mode query
- [ ] Test A3: NEIGHBORHOOD mode query
- [ ] Test A4: Exchange filter

### GCS Tests (if configured)
- [ ] Test B1: GCS upload (default)
- [ ] Test B2: Local mode with --output
- [ ] Test B3: Graceful fallback (invalid creds)
- [ ] Test B4: Graceful fallback (bucket not found)
- [ ] Test B5: GCS not configured
- [ ] Test B6: Large file upload

### Output Format Tests
- [ ] Test C1: Unified filename format
- [ ] Test C2: Metadata structure

### Error Handling Tests
- [ ] Test D1: Invalid symbol format
- [ ] Test D2: Missing timestamp predicate
- [ ] Test D3: Retry logic
- [ ] Test D4: GCS permission denied

### Request Tracking Tests
- [ ] Test E1: Request ID consistency
- [ ] Test E2: Concurrent requests

### Performance Tests
- [ ] Small query (< 5s)
- [ ] Medium query (< 10s)
- [ ] Large query (< 30s)
- [ ] GCS upload (< 10s for typical file)

---

## Quick Start Testing Script

```bash
#!/bin/bash
# Quick integration test script

echo "=== Integration Test Suite ==="

# Test 1: Local mode
echo "Test 1: Local mode with --output"
python main.py --symbol BTCUSDT --timeframe 1d --all --output ./test-output
echo "Exit code: $?"
echo ""

# Test 2: Default mode (GCS if configured, local otherwise)
echo "Test 2: Default mode"
python main.py --symbol ETHUSDT --timeframe 1h \
  --from 2024-01-01T00:00:00Z --to 2024-01-31T23:59:59Z
echo "Exit code: $?"
echo ""

# Test 3: Error handling
echo "Test 3: Invalid symbol (should fail gracefully)"
python main.py --symbol invalid-symbol --timeframe 1d --all 2>&1 | head -20
echo "Exit code: $?"
echo ""

# Verify output files
echo "=== Generated Files ==="
ls -lh ./*.json ./test-output/*.json 2>/dev/null || echo "No files found"

echo ""
echo "=== Test Complete ==="
```

---

## Next Steps

After successful integration testing:
1. Run with production credentials (if different from dev)
2. Set up monitoring/alerting for errors
3. Configure production GCS bucket with appropriate lifecycle policies
4. Integrate with Loki for log aggregation (future enhancement)
5. Consider adding more query modes or filters as needed
6. Set up automated integration tests with test bucket

