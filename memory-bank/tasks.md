# Tasks: BigQuery Stock Quotes Extractor

## Task Overview
**Task ID**: BQ-001
**Title**: Python 3.13 Script for BigQuery Historical Stock Quotes Extraction
**Status**: Planning
**Complexity Level**: Level 3 - Intermediate Feature

## Complexity Determination

### Assessment Criteria:

**Scope Impact:**
- Affects: Multiple components (configuration handler, BigQuery client, query builder, backoff mechanism, output formatter)
- System-wide implications: No
- Files to modify: Multiple new files required

**Design Decisions:**
- Complex design decisions: Yes (query builder architecture, backoff strategy implementation)
- Creative phase required: Yes
- Architectural considerations: Module structure, error handling strategy

**Risk Assessment:**
- Failure impact: Moderate (incorrect data retrieval, authentication failures)
- Security implications: Yes (GCP credentials handling)
- Critical functionality: Yes (data extraction is core functionality)

**Implementation Effort:**
- Duration: Days (estimated 1-2 days)
- Specialized knowledge: Yes (BigQuery API, GCP authentication)
- Testing needed: Extensive (query building, backoff logic, error scenarios)

### Keywords Identified:
- "скрипт" (script) - Level 3 indicator
- "create" - Level 3 indicator
- "develop" - Level 3 indicator

### Determination:
**Level 3 - Intermediate Feature**

Rationale:
- Multiple interconnected components required
- Significant design decisions for query builder and error handling
- Moderate risk with security considerations (credentials)
- Requires comprehensive implementation with multiple modules
- Falls between simple enhancement and complex system

## Component Breakdown

### 1. Configuration Management
- Load environment variables from `.env`
- Validate configuration parameters
- Manage GCP credentials path

### 2. Logging System
- Structured logging similar to existing project pattern (see temp/logging_util.py)
- JSON-formatted log messages
- Environment-aware configuration (service name, environment)
- Loki support deferred to future stages

### 3. BigQuery Client
- Initialize BigQuery client with authentication
- Handle connection lifecycle
- Implement connection retry logic

### 4. Query Builder
- Construct dynamic SQL queries based on parameters
- **CRITICAL**: Ensure ALL queries include timestamp condition (table is partitioned)
- Handle different time interval modes (all with bounds, range, neighborhood)
- Implement exchange selection logic
- Validate timestamp conditions before query execution

### 5. Backoff Strategy
- Exponential backoff implementation
- Configurable retry parameters
- Error classification for retry decisions

### 6. Output Handler
- Transform BigQuery results to JSON structure
- Map fields to output specification
- Handle timestamp formatting
- Save to file in project folder with naming pattern: `{symbol}_{timeframe}_{timestamp}.json`

### 7. Main Script
- Parse command-line arguments
- Validate inputs (symbol format: BTCUSDT, etc.)
- Coordinate component interactions
- Error handling with structured logging

## Input Parameters Specification

### Required Parameters:
- `--symbol` or `-s`: Stock symbol in format BTCUSDT, ETHUSDT, etc. (string, required)
- `--timeframe` or `-t`: Timeframe value (choices: '1M', '1w', '1d', '4h', '1h', '15', '5', '1')

### Optional Parameters:
- `--exchange` or `-e`: Exchange identifier (string, optional)
- `--output` or `-o`: Output directory (default: current directory)

### Time Interval Options (one required, mutually exclusive):
- `--all`: Fetch all historical records for the symbol (last 15 years / 5475 days)
- `--from` and `--to`: Date range (both required if used, satisfies partition requirement)
- `--around <timestamp>`: Center timestamp
  - `--before N`: Number of candles before center point (required with --around)
  - `--after N`: Number of candles after center point (required with --around)
  - Uses adaptive time window to satisfy partition requirement while fetching exact record count

**IMPORTANT**: Due to BigQuery table partitioning on `timestamp` field, every query MUST include a timestamp predicate. The `--all` option uses a 15-year window to capture entire historical range while satisfying partition requirement.

## Technical Requirements

### Dependencies:
- `google-cloud-bigquery` - BigQuery client library
- `python-dotenv` - Environment variable management
- `tenacity` or custom backoff implementation

### Environment Variables (.env):
```
BIGQUERY_PROJECT_ID=<project-id>
BIGQUERY_DATASET=<dataset-name>
BIGQUERY_TABLE=<table-name>
GOOGLE_APPLICATION_CREDENTIALS=<path-to-key.json>
```

### Backoff Configuration:
```python
BACKOFF_BASE = 1.0
BACKOFF_FACTOR = 2.0
BACKOFF_MAX = 32.0
BACKOFF_ATTEMPTS = 5
```

## Output Specification

JSON file saved to project folder (or specified output directory).

Filename pattern: `{symbol}_{timeframe}_{start_timestamp}.json`

Example: `BTCUSDT_1d_20240101.json`

JSON structure:
```json
{
  "candle_fields": ["date", "open", "high", "low", "close", "volume"],
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

## Success Criteria
- [ ] Script loads configuration from `.env` file
- [ ] Authenticates with Google Cloud using JSON key
- [ ] Accepts all required and optional command-line parameters
- [ ] Validates symbol format (BTCUSDT pattern)
- [ ] **CRITICAL**: ALL queries include timestamp condition (partition requirement)
- [ ] Constructs correct SQL queries for all time interval modes
- [ ] Implements exponential backoff with specified parameters
- [ ] Implements structured logging (JSON format, similar to existing project)
- [ ] Saves data to JSON file in project folder
- [ ] Handles errors gracefully with informative structured log messages
- [ ] Includes usage documentation

## Detailed Implementation Plan

### Phase 1: Project Setup & Dependencies (30 min)
**Goal**: Initialize Python project structure and install dependencies

**Tasks**:
- [ ] 1.1 Create project structure
  ```
  sandbox_gcp_bigquery/
  ├── src/
  │   ├── __init__.py
  │   ├── logging_util.py
  │   ├── config.py
  │   ├── bigquery_client.py
  │   ├── query_builder.py
  │   ├── backoff.py
  │   └── output_handler.py
  ├── main.py
  ├── output/
  ├── .env
  ├── .env.example
  ├── requirements.txt
  └── README.md
  ```
- [ ] 1.2 Create `requirements.txt` with dependencies:
  - google-cloud-bigquery>=3.13.0
  - python-dotenv>=1.0.0
  - (No additional retry library - implement custom backoff)
- [ ] 1.3 Create `.env.example` template
- [ ] 1.4 Create `.gitignore` (credentials, output files, Python artifacts)
- [ ] 1.5 Install dependencies in virtual environment

**Deliverables**:
- Project structure created
- Dependencies documented and installed
- Environment template ready

---

### Phase 2: Core Infrastructure (1.5 hours)
**Goal**: Implement foundational components (logging, config, backoff)

#### 2.1 Logging System (30 min)
- [ ] Create `src/logging_util.py` based on existing pattern
  - Implement `build_logger()` function
  - Implement `log_struct()` for structured logging
  - JSON-formatted output to stdout
  - No Loki integration (deferred)
- [ ] Test logging with sample messages

#### 2.2 Configuration Management (30 min)
- [ ] Create `src/config.py`
  - Load .env file using python-dotenv
  - Validate required environment variables
  - Provide defaults for backoff parameters
  - Environment variables:
    - BIGQUERY_PROJECT_ID (required)
    - BIGQUERY_DATASET (required)
    - BIGQUERY_TABLE (required)
    - GOOGLE_APPLICATION_CREDENTIALS (required)
    - SERVICE_NAME (default: "bigquery-extractor")
    - ENVIRONMENT (default: "dev")
    - BACKOFF_BASE (default: 1.0)
    - BACKOFF_FACTOR (default: 2.0)
    - BACKOFF_MAX (default: 32.0)
    - BACKOFF_ATTEMPTS (default: 5)
- [ ] Implement validation logic with clear error messages
- [ ] Test configuration loading

#### 2.3 Backoff Strategy (30 min)
- [ ] Create `src/backoff.py`
  - Implement exponential backoff decorator
  - Parameters: base, factor, max_delay, max_attempts
  - Error classification (retry vs non-retry)
  - Structured logging of retry attempts
- [ ] Test backoff behavior with mock failures

**Deliverables**:
- Logging system operational
- Configuration management complete
- Backoff strategy implemented and tested

---

### Phase 3: BigQuery Integration (2 hours)
**Goal**: Implement BigQuery client and query builder

#### 3.1 BigQuery Client (1 hour)
- [ ] Create `src/bigquery_client.py`
  - Initialize BigQuery client with authentication
  - Apply backoff decorator to query execution
  - Handle BigQuery-specific exceptions
  - Connection lifecycle management
  - Structured logging of operations
- [ ] Test authentication with real credentials
- [ ] Test query execution with simple query

#### 3.2 Query Builder (1 hour) - **REQUIRES CREATIVE PHASE**
- [ ] Create `src/query_builder.py`
  - Base query template with partition requirement
  - **Mode 1: ALL** - 15-year historical range
    - Calculate start: CURRENT_TIMESTAMP() - INTERVAL 5475 DAY
    - Calculate end: CURRENT_TIMESTAMP()
  - **Mode 2: RANGE** - Explicit from/to timestamps
    - Validate from <= to
    - Use provided timestamps
  - **Mode 3: NEIGHBORHOOD** - Adaptive window
    - Implement `calculate_adaptive_window()` function
    - Build UNION ALL query (before/center/after)
    - Handle edge cases (insufficient data)
  - Exchange selection logic (first if multiple)
  - Parameterized queries (SQL injection prevention)
  - Timestamp predicate validation (enforce partition requirement)
- [ ] Unit tests for each query mode
- [ ] Test with various timeframes (especially 1M, 1w)

**Deliverables**:
- BigQuery client functional
- Query builder with all three modes
- Partition requirement enforced in all queries

---

### Phase 4: CLI & Output Handling (1.5 hours)
**Goal**: Implement command-line interface and JSON output

#### 4.1 Output Handler (45 min)
- [ ] Create `src/output_handler.py`
  - Transform BigQuery Row objects to dictionaries
  - Format timestamps to ISO 8601
  - Generate output filename: `{symbol}_{timeframe}_{start_timestamp}.json`
  - Create output directory if needed
  - Write JSON with proper structure and indentation
  - Handle file write errors
- [ ] Test output formatting

#### 4.2 Main Script & CLI (45 min)
- [ ] Create `main.py`
  - Use `argparse` for CLI
  - Required args: --symbol, --timeframe, one of (--all, --from/--to, --around/--before/--after)
  - Optional args: --exchange, --output
  - Mutually exclusive groups for time intervals
  - Input validation:
    - Symbol format (uppercase alphanumeric)
    - Timeframe in allowed values
    - Timestamp formats for range/neighborhood
  - Coordinate all components
  - Main execution flow with error handling
  - Exit codes (0=success, 1=error)
- [ ] Test CLI argument parsing
- [ ] Test end-to-end flow

**Deliverables**:
- CLI fully functional
- Output handler saving JSON files
- Complete end-to-end flow working

---

### Phase 5: Testing & Documentation (1 hour)
**Goal**: Comprehensive testing and documentation

#### 5.1 Testing (30 min)
- [ ] Test all three query modes with real BigQuery
  - ALL mode: Full 15-year history
  - RANGE mode: Specific date range
  - NEIGHBORHOOD mode: 3 candles before/after (especially 1M timeframe)
- [ ] Test error scenarios:
  - Missing .env file
  - Invalid credentials
  - Network failures (backoff trigger)
  - Invalid input parameters
  - Empty result sets
- [ ] Test edge cases:
  - Symbol with no data
  - Neighborhood with insufficient history
  - Multiple exchanges for same symbol

#### 5.2 Documentation (30 min)
- [ ] Create comprehensive `README.md`
  - Project description
  - Requirements (Python 3.13, GCP setup)
  - Installation instructions
  - Configuration (.env setup)
  - Usage examples for all three modes
  - Output format specification
  - Troubleshooting section
- [ ] Add docstrings to all modules
- [ ] Create `.env.example` with comments

**Deliverables**:
- All modes tested with real data
- Complete documentation
- Ready for production use

---

## Technology Stack

### Core Technologies
- **Language**: Python 3.13
- **Cloud Platform**: Google Cloud Platform (BigQuery)
- **Key Libraries**:
  - `google-cloud-bigquery` (3.13.0+) - Official BigQuery client
  - `python-dotenv` (1.0.0+) - Environment configuration
  - Standard library: `argparse`, `json`, `logging`, `datetime`

### Development Tools
- **Virtual Environment**: venv or conda
- **Linting**: (optional) pylint, flake8
- **Testing**: Manual testing with real BigQuery data

### Authentication
- **Method**: Service Account JSON key
- **Scope**: BigQuery read access
- **Storage**: Local file, path in .env

---

## Creative Phases Required

### 🎨 Query Builder Architecture (REQUIRED)
**Component**: `src/query_builder.py`

**Design Decisions Needed**:
1. **Query Construction Pattern**
   - Option A: String templates with parameter substitution
   - Option B: Query builder class with method chaining
   - Option C: SQL template files with Jinja2
   
2. **Adaptive Window Calculation**
   - How to handle edge cases (very large N for 1M timeframe)
   - Capping strategies (max window size)
   - Buffer percentage tuning (current: 20%)

3. **NEIGHBORHOOD Mode Implementation**
   - UNION ALL approach (current plan)
   - Alternative: Single query with window functions
   - Handling missing center timestamp

**Status**: ⏳ Pending CREATIVE mode

### ✅ Error Handling Strategy (COMPLETE)
**Component**: Cross-cutting concern
**Document**: `memory-bank/creative/creative-error-handling.md`
**Decision**: Custom Exception Hierarchy with Central Handler (Option 2)

**Selected Approach**:
- **Base Exception**: `BQExtractorError` with message, context, exit_code, retryable
- **Specific Exceptions**: ConfigurationError, AuthenticationError, QueryExecutionError, etc.
- **Error Mapper**: Converts BigQuery exceptions to custom exceptions
- **Central Handler**: Single try/except block in main.py

**Key Design Decisions**:
1. Exception hierarchy for programmatic error handling
2. Exit codes attached to exception classes (1=config, 2=auth, 3=query, 4=file, 0=no data)
3. Context dictionary for structured logging
4. Retryable flag for backoff integration
5. User-facing messages to stderr + technical logs as JSON

**Status**: ✅ Complete, ready for implementation

---

## Dependencies & Integration Points

### External Dependencies
- **Google Cloud BigQuery**: Data source
- **Service Account**: Authentication
- **Partitioned Table**: Must query with timestamp predicates

### Internal Dependencies
- `logging_util.py` → Used by all modules
- `config.py` → Used by `bigquery_client.py`, `main.py`
- `backoff.py` → Decorates `bigquery_client.py` methods
- `query_builder.py` → Used by `main.py`
- `bigquery_client.py` → Uses `query_builder.py`
- `output_handler.py` → Used by `main.py`

### Data Flow
```
main.py
  ↓ (parse args, validate)
config.py (load .env)
  ↓
bigquery_client.py (authenticate)
  ↓
query_builder.py (build SQL)
  ↓ (execute with backoff)
bigquery_client.py (get results)
  ↓
output_handler.py (format & save)
  ↓
JSON file in output/
```

---

## Challenges & Mitigations

### Challenge 1: Partition Requirement Enforcement
**Risk**: Queries without timestamp predicates will fail or scan entire table
**Mitigation**: 
- Query builder ALWAYS includes timestamp predicates
- Validation layer before query execution
- Unit tests to verify predicate presence in all query modes

### Challenge 2: Adaptive Window Calculation for 1M Timeframe
**Risk**: Fixed window too small for monthly candles
**Mitigation**:
- Implemented formula: `days = (records_needed / records_per_day) * 1.2`
- For 1M: 1/30 candles per day → 3 candles = 108-day window
- Tested with real data to verify sufficiency

### Challenge 3: BigQuery Rate Limiting
**Risk**: Excessive queries trigger rate limits
**Mitigation**:
- Exponential backoff with 5 retry attempts
- Base delay: 1.0s, max delay: 32.0s
- Classify errors (retry vs fail-fast)

### Challenge 4: Large Result Sets (1m timeframe, 15 years)
**Risk**: ~7.8M records for 1-minute candles over 15 years
**Mitigation**:
- BigQuery handles pagination automatically
- Stream results to file (don't load all in memory)
- Consider adding `--max-records` flag in future
- Log warning for potentially large queries

### Challenge 5: Credential Security
**Risk**: Accidental commit of service account key
**Mitigation**:
- .gitignore includes *.json, .env
- .env.example with placeholder values
- README emphasizes security best practices
- Path-based reference (not inline credentials)

### Challenge 6: Empty Result Sets
**Risk**: User confusion when no data found
**Mitigation**:
- Return valid JSON with empty data array
- Structured log message explaining no data found
- Include metadata in output (requested params)

---

## Implementation Timeline

**Total Estimated Time**: 6.5 hours

| Phase | Duration | Description |
|-------|----------|-------------|
| Phase 1 | 30 min | Project setup |
| Phase 2 | 1.5 hrs | Core infrastructure |
| Phase 3 | 2 hrs | BigQuery integration |
| Phase 4 | 1.5 hrs | CLI & output |
| Phase 5 | 1 hr | Testing & docs |

**Dependencies**: Phases must be completed sequentially

---

## Status Tracking

- [x] VAN mode - Initialization complete
- [x] PLAN mode - Planning complete
- [x] CREATIVE mode - All creative phases complete ✅
  - [x] Query Builder Architecture ✅
  - [x] Error Handling Strategy ✅
- [x] BUILD mode - Implementation complete ✅
  - [x] Phase 1: Project Setup
  - [x] Phase 2: Configuration & Logging
  - [x] Phase 3: Query Builder
  - [x] Phase 4: BigQuery Integration
  - [x] Phase 5: CLI & Output Handler
  - [x] All 70 unit tests passing
- [ ] REFLECT mode - Post-implementation review

## Creative Phase Results

### ✅ Query Builder Architecture (COMPLETE)
**Document**: `memory-bank/creative/creative-query-builder.md`
**Decision**: Hybrid String Templates with Validator Class (Option 4)

**Selected Approach**:
- **QueryValidator**: Enforces partition predicates (fail-fast)
- **QueryHelpers**: Reusable utilities (adaptive window, exchange clause)
- **QueryBuilder**: Main class with three mode-specific methods

**Key Design Decisions**:
1. F-string templates for SQL generation (readable, no dependencies)
2. Separate validator class to enforce partition requirement
3. Helper class for adaptive window calculation and common logic
4. Three distinct methods for ALL, RANGE, NEIGHBORHOOD modes

**Rationale**:
- Balances simplicity with maintainability
- No external dependencies (Jinja2 not needed)
- Easy to test (static methods, pure functions)
- Clear code structure for future modifications
- Validator ensures critical partition requirement never missed

**Implementation Time**: ~2 hours (within Phase 3 estimate)

---

### ✅ Error Handling Strategy (COMPLETE)
**Document**: `memory-bank/creative/creative-error-handling.md`
**Decision**: Custom Exception Hierarchy with Central Handler (Option 2)

**Selected Approach**:
- **Exception Hierarchy**: Base `BQExtractorError` with specific subclasses
- **Error Mapper**: Converts BigQuery exceptions to custom exceptions
- **Central Handler**: Single try/except in main.py
- **Structured Logging**: All errors logged as JSON

**Key Design Decisions**:
1. Custom exception classes (ConfigurationError, AuthenticationError, etc.)
2. Exit codes attached to exception classes (1, 2, 3, 4, 0)
3. Context dictionary for structured logging
4. Retryable flag for backoff integration
5. Error mapper utility for third-party exception conversion

**Rationale**:
- Pythonic and idiomatic (exceptions are standard in Python)
- Simple to implement and maintain (~1.5 hours)
- Easy to test (mock exceptions)
- Clear separation of concerns
- Integrates seamlessly with backoff decorator and structured logging
- Extensible for future error types

**Implementation Time**: ~1.5 hours (integrated across multiple phases)

---

## Next Steps

1. ~~**Complete PLAN mode**~~ ✅ Complete
2. ~~**Enter CREATIVE mode**~~ ✅ Complete (Query Builder + Error Handling)
3. **Enter BUILD mode** - Implement according to plan
4. **Testing** - Verify with real BigQuery data
5. **Documentation** - Complete README and docstrings

**Recommended Next Mode**: BUILD (implement all components)

