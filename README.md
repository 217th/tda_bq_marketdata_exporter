# BigQuery Stock Quotes Extractor

Python 3.13 script for extracting historical stock quotes from Google BigQuery with support for multiple query modes and exponential backoff retry logic.

## Features

- **Multiple Query Modes**:
  - **ALL**: Retrieve 15 years of historical data
  - **RANGE**: Retrieve data within a specific time range
  - **NEIGHBORHOOD**: Retrieve N records before and after a timestamp
- **Cloud Storage Output**: Automatic upload to Google Cloud Storage with public download URLs
- **Adaptive Time Windows**: Automatically calculates optimal query windows based on timeframe
- **Exponential Backoff**: Configurable retry logic for BigQuery API calls
- **Structured Logging**: JSON-formatted logs for observability with automatic request ID tracking
- **Request Correlation**: Every extraction receives a unique request ID included in all log messages
- **Flexible Output**: GCS bucket (default) or local filesystem (with `--output` flag)

## Requirements

- Python 3.13+
- Google Cloud Platform account with BigQuery access
- BigQuery service account key JSON file (for data queries)
- Google Cloud Storage bucket (optional, for cloud output)
- GCS service account key JSON file (optional, for cloud uploads)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp env.example .env

# Edit .env with your credentials
nano .env
```

## Configuration

Edit `.env` file:

### BigQuery Configuration (Required)

```env
GCP_PROJECT_ID=your-project-id
BQ_DATASET=your_dataset_name
BQ_TABLE=your_table_name
GCP_KEY_PATH=/path/to/bigquery-service-account-key.json
SERVICE_NAME=bq-stock-extractor
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Google Cloud Storage Configuration (Optional)

If you want output files automatically uploaded to GCS:

```env
GCS_BUCKET_NAME=your-bucket-name
GCS_SERVICE_ACCOUNT_KEY=/path/to/gcs-service-account-key.json
```

**Important Notes:**
- GCS service account must have `Storage Object Creator` and `Storage Object Viewer` roles
- Bucket should have `allUsers` with `Storage Object Viewer` permission for public downloads
- If GCS is not configured, files will be saved locally (same as using `--output` flag)

## Usage

### Output Modes

**Default Mode (GCS Upload):**
When GCS is configured and `--output` flag is NOT provided, the script uploads results to Google Cloud Storage:

```bash
# Upload to GCS bucket (default if GCS configured)
python main.py --symbol BTCUSDT --timeframe 1d --all

# Result:
# ✅ Success! Data uploaded to GCS:
#    Download URL: https://storage.googleapis.com/your-bucket/abc-123-def-456.json
#    Records: 365
```

**Local Mode (Filesystem):**
Use `--output` flag to save locally instead of GCS:

```bash
# Save to local filesystem
python main.py --symbol BTCUSDT --timeframe 1d --all --output ./data/

# Result:
# ✅ Success! Data saved locally:
#    File: ./data/abc-123-def-456.json
#    Records: 365
```

### Query Examples

#### Query All Data (15 years)
```bash
# To GCS (default if configured):
python main.py --symbol BTCUSDT --timeframe 1d --all

# To local filesystem:
python main.py --symbol BTCUSDT --timeframe 1d --all --output ./data/
```

#### Query Time Range
```bash
python main.py --symbol ETHUSDT --timeframe 1h \
  --from 2024-01-01T00:00:00Z \
  --to 2024-12-31T23:59:59Z
```

#### Query Neighborhood
```bash
python main.py --symbol BTCUSDT --timeframe 15 \
  --timestamp 2024-06-15T12:00:00Z \
  --n-before 100 \
  --n-after 100
```

### Optional Parameters
```bash
--exchange BINANCE      # Specify exchange (optional)
--output ./data/        # Save to local directory instead of GCS (optional)
```

## Output Format

### File Naming

All output files use the same naming pattern:
- **Filename**: `{request_id}.json` (e.g., `550e8400-e29b-41d4-a716-446655440000.json`)
- **request_id**: Unique UUID4 generated for each extraction request
- **Applies to**: Both GCS and local filesystem modes

### JSON Structure

The output JSON includes metadata about the request along with the OHLCV candle data:

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

### Metadata Fields

- **request_id**: Unique identifier for this extraction request (UUID4)
- **request_timestamp**: When the request was initiated (ISO 8601 format)
- **symbol**: Stock symbol that was queried
- **timeframe**: Timeframe value used in the query
- **query_type**: Type of query executed (`all`, `range`, or `neighborhood`)
- **query_parameters**: Query-specific parameters (varies by query type)

### Query Parameters by Type

**ALL Query** (no parameters):
```json
"query_parameters": {}
```

**RANGE Query**:
```json
"query_parameters": {
  "from_timestamp": "2024-01-01T00:00:00Z",
  "to_timestamp": "2024-12-31T23:59:59Z"
}
```

**NEIGHBORHOOD Query**:
```json
"query_parameters": {
  "center_timestamp": "2024-06-15T10:30:00Z",
  "n_before": 10,
  "n_after": 10
}
```

## Request Tracking

Each extraction request automatically receives a unique request ID (UUID4) that is included in all log messages. This enables:
- **Request Correlation**: Track all log entries for a specific extraction
- **Distributed Tracing**: Correlate logs across systems
- **Debugging**: Quickly identify all logs related to a failed request

### Example Log Output with Request ID

```json
{
  "timestamp": "2025-12-12T10:30:00.123456Z",
  "level": "INFO",
  "logger": "bq-stock-extractor",
  "message": "Starting BigQuery extraction in ALL mode",
  "request_id": "a3b8c9d7-e4f5-4a6b-8c9d-7e8f9a0b1c2d",
  "labels": {
    "service": "bq-stock-extractor",
    "environment": "development",
    "symbol": "BTCUSDT",
    "timeframe": "1d",
    "mode": "ALL"
  },
  "fields": {
    "exchange": null,
    "output_dir": "."
  }
}
```

The same `request_id` will appear in all subsequent log messages for that extraction, making it easy to filter and correlate logs in log aggregation systems like Loki, Elasticsearch, or CloudWatch.

## Backoff Configuration

Default retry parameters:
- Base delay: 1.0 seconds
- Factor: 2.0 (exponential)
- Max delay: 32.0 seconds
- Max attempts: 5

## Project Structure

```
sandbox_gcp_bigquery/
├── src/
│   ├── config.py           # Configuration loader
│   ├── logger.py           # Structured logging
│   ├── exceptions.py       # Custom exceptions
│   ├── error_mapper.py     # BigQuery error mapping
│   ├── query_builder.py    # SQL query construction
│   ├── bigquery_client.py  # BigQuery client with retry
│   └── output_handler.py   # JSON output handler
├── tests/
│   └── test_*.py           # Unit tests
├── main.py                 # CLI entry point
├── requirements.txt        # Dependencies
└── .env                    # Configuration (not in git)
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## License

MIT

