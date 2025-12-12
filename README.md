# BigQuery Stock Quotes Extractor

Python 3.13 script for extracting historical stock quotes from Google BigQuery with support for multiple query modes and exponential backoff retry logic.

## Features

- **Multiple Query Modes**:
  - **ALL**: Retrieve 15 years of historical data
  - **RANGE**: Retrieve data within a specific time range
  - **NEIGHBORHOOD**: Retrieve N records before and after a timestamp
- **Adaptive Time Windows**: Automatically calculates optimal query windows based on timeframe
- **Exponential Backoff**: Configurable retry logic for BigQuery API calls
- **Structured Logging**: JSON-formatted logs for observability
- **Flexible Output**: JSON files with customizable naming

## Requirements

- Python 3.13+
- Google Cloud Platform account with BigQuery access
- Service account key JSON file

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

```env
GCP_PROJECT_ID=your-project-id
BQ_DATASET=your_dataset_name
BQ_TABLE=your_table_name
GCP_KEY_PATH=/path/to/service-account-key.json
SERVICE_NAME=bq-stock-extractor
ENVIRONMENT=development
LOG_LEVEL=INFO
```

## Usage

### Query All Data (15 years)
```bash
python main.py --symbol BTCUSDT --timeframe 1d --all
```

### Query Time Range
```bash
python main.py --symbol ETHUSDT --timeframe 1h \
  --from 2024-01-01T00:00:00Z \
  --to 2024-12-31T23:59:59Z
```

### Query Neighborhood
```bash
python main.py --symbol BTCUSDT --timeframe 15 \
  --timestamp 2024-06-15T12:00:00Z \
  --n-before 100 \
  --n-after 100
```

### Optional Parameters
```bash
--exchange BINANCE      # Specify exchange (optional)
--output ./data/        # Output directory (default: current)
```

## Output Format

Output file: `{symbol}_{timeframe}_{start_timestamp}.json`

```json
[
  {
    "date": "2024-01-01T00:00:00Z",
    "open": 42000.5,
    "high": 42500.0,
    "low": 41800.0,
    "close": 42300.0,
    "volume": 1234.56
  }
]
```

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

