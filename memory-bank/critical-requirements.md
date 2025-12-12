# Critical Requirements

## 🚨 MANDATORY REQUIREMENTS - DO NOT SKIP

### 1. Table Partition Requirement
**CRITICAL**: The BigQuery table is partitioned by the `timestamp` field.

**Implication**: Every query MUST include a predicate on the `timestamp` column. Queries without timestamp predicates will:
- Scan the entire table (expensive and slow)
- May fail with partition requirement errors
- Violate BigQuery best practices

**Implementation Impact**:
- Even `--all` option must use reasonable default time bounds
- Query builder must validate timestamp predicates exist before execution
- All three query modes (all, range, neighborhood) must include timestamp filters

### 2. Symbol Format
**Format**: Cryptocurrency pair format like `BTCUSDT`, `ETHUSDT`, `BNBUSDT`
- No spaces or separators
- Uppercase recommended
- Base currency + quote currency concatenated

### 3. Output Format
**NOT stdout** - Save to JSON file in project folder

**File naming**: `{symbol}_{timeframe}_{start_timestamp}.json`

Example: `BTCUSDT_1d_20240101.json`

### 4. Logging Approach
**Follow existing project pattern** (see temp/logging_util.py):
- Structured JSON logging
- Service name and environment labels
- Console output (StreamHandler)
- **Loki integration deferred** - do not implement Loki handler initially

## Query Validation Checklist

Before executing any BigQuery query, verify:
- [ ] Query includes `timestamp >= @start_time` or similar
- [ ] Query includes `timestamp <= @end_time` or similar
- [ ] Timestamp bounds are reasonable (not unbounded)
- [ ] Symbol parameter is provided
- [ ] Timeframe parameter is provided

## Default Behaviors

### --all flag behavior:
```python
# DO THIS - используем весь исторический диапазон (15 лет):
start_time = datetime.now() - timedelta(days=15*365)  # 15 лет истории
end_time = datetime.now()

# DON'T DO THIS - нет timestamp фильтра (провалится или просканирует всю таблицу):
# WHERE symbol = @symbol AND timeframe = @timeframe  # ❌ Нет timestamp!
```

### Neighborhood query:
```python
# DO THIS - адаптивное окно в зависимости от timeframe и количества записей:

def calculate_adaptive_window(timeframe: str, records_needed: int) -> int:
    """Вычисляет окно в днях для получения нужного количества свечей."""
    records_per_day = {
        '1M': 1/30,   # месячная свеча: ~1 свеча в 30 дней
        '1w': 1/7,    # недельная свеча: ~1 свеча в 7 дней
        '1d': 1,      # дневная свеча: 1 свеча в день
        '4h': 6,      # 4-часовая: 6 свечей в день
        '1h': 24,     # часовая: 24 свечи в день
        '15': 96,     # 15-минутная: 96 свечей в день
        '5': 288,     # 5-минутная: 288 свечей в день
        '1': 1440,    # 1-минутная: 1440 свечей в день
    }
    rpd = records_per_day.get(timeframe, 1)
    days_needed = int((records_needed / rpd) * 1.2)  # +20% запас
    return max(1, min(5475, days_needed))  # от 1 дня до 15 лет

# Примеры расчёта:
# - timeframe='1M', n=3:   days = (3 / (1/30)) * 1.2 = 108 дней (~3.6 месяца)
# - timeframe='1w', n=10:  days = (10 / (1/7)) * 1.2 = 84 дня (~12 недель)
# - timeframe='1d', n=100: days = (100 / 1) * 1.2 = 120 дней
# - timeframe='1h', n=100: days = (100 / 24) * 1.2 = 5 дней

window_days = calculate_adaptive_window(timeframe, max(n_before, n_after))

# 1. Записи ДО центра
query_before = """
SELECT timestamp, open, high, low, close, volume
FROM `{project}.{dataset}.{table}`
WHERE symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp < @center_timestamp
  AND timestamp >= TIMESTAMP_SUB(@center_timestamp, INTERVAL @window_days DAY)
ORDER BY timestamp DESC
LIMIT @n_before
"""

# 2. Записи ПОСЛЕ центра
query_after = """
SELECT timestamp, open, high, low, close, volume
FROM `{project}.{dataset}.{table}`
WHERE symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp > @center_timestamp
  AND timestamp <= TIMESTAMP_ADD(@center_timestamp, INTERVAL @window_days DAY)
ORDER BY timestamp ASC
LIMIT @n_after
"""

# 3. Центральная свеча (опционально)
query_center = """
SELECT timestamp, open, high, low, close, volume
FROM `{project}.{dataset}.{table}`
WHERE symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp = @center_timestamp
LIMIT 1
"""
```

**DON'T DO THIS** - фиксированное окно не работает для всех таймфреймов:
```python
# ❌ Плохо - 30 дней это только 1 свеча для 1M timeframe!
window = timedelta(days=30)

# ❌ Плохо - временная дельта даёт непредсказуемое количество записей
window = timedelta(days=7)
```

## Environment Variables

Required in `.env`:
```bash
# BigQuery
BIGQUERY_PROJECT_ID=your-project
BIGQUERY_DATASET=your-dataset
BIGQUERY_TABLE=your-table
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

# Logging
SERVICE_NAME=bigquery-extractor
ENVIRONMENT=dev

# Backoff (optional, use defaults if not specified)
BACKOFF_BASE=1.0
BACKOFF_FACTOR=2.0
BACKOFF_MAX=32.0
BACKOFF_ATTEMPTS=5

# Query defaults
DEFAULT_TIME_RANGE_DAYS=5475  # 15 years for --all queries (15 * 365)
```

## Error Scenarios to Handle

1. **Missing timestamp predicate**: Validate before sending to BigQuery
2. **Invalid symbol format**: Validate format before querying
3. **No data found**: Return empty data array, log warning
4. **Multiple exchanges**: Log which exchange was selected
5. **Authentication failure**: Structured log with clear error message
6. **Rate limiting**: Apply backoff strategy
7. **File write failure**: Log error, suggest alternative output path

