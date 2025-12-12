# Creative Phase: Query Builder Architecture

**Component**: `src/query_builder.py`  
**Date**: December 11, 2024  
**Status**: ✅ Complete  
**Decision**: Hybrid String Templates with Validator Class (Option 4)

---

## 🎯 Problem Statement

Design a maintainable, flexible SQL query construction system that:
- Generates parameterized BigQuery SQL queries
- Enforces timestamp partition predicates (MANDATORY requirement)
- Supports three distinct query modes (ALL, RANGE, NEIGHBORHOOD)
- Calculates adaptive time windows based on timeframe
- Handles edge cases and validates inputs
- Remains testable and debuggable

**Context**: BigQuery table is partitioned by timestamp field. ALL queries must include timestamp predicates to avoid full table scans and ensure query performance.

---

## 📊 Options Analysis

### Option 1: String Template with Functions ⭐ Simple

**Approach**: Use Python f-strings with separate function per query mode.

**Pros**:
- ✅ Very simple and straightforward
- ✅ Easy to read SQL directly in code
- ✅ Minimal abstraction overhead
- ✅ Easy to debug

**Cons**:
- ❌ Code duplication across methods
- ❌ Scattered validation logic
- ❌ No reusable helpers

**Complexity**: Low  
**Time**: 1.5 hours

---

### Option 2: Builder Class with Method Chaining 🔗 Flexible

**Approach**: Fluent interface with chainable methods (`.select()`, `.where()`, etc.)

**Pros**:
- ✅ Highly modular and composable
- ✅ Reusable query building blocks
- ✅ Clear separation of concerns

**Cons**:
- ❌ More complex for simple use cases
- ❌ State management overhead
- ❌ Less obvious for NEIGHBORHOOD mode
- ❌ Harder to visualize final query

**Complexity**: Medium-High  
**Time**: 3 hours

---

### Option 3: Template Files with Jinja2 📄 Separated

**Approach**: SQL templates in separate files, rendered with Jinja2.

**Pros**:
- ✅ Clean separation of SQL from Python
- ✅ Easy for SQL experts to modify

**Cons**:
- ❌ External dependency (Jinja2)
- ❌ Extra file management
- ❌ Harder to debug (split locations)
- ❌ Overkill for this use case

**Complexity**: High  
**Time**: 2.5 hours

---

### Option 4: Hybrid String Templates with Validator ✅ SELECTED

**Approach**: Combine string templates with separate Helper and Validator classes.

**Architecture**:
```python
QueryValidator  # Enforces partition predicates
QueryHelpers    # Reusable utilities (adaptive window, exchange)
QueryBuilder    # Main class with mode-specific methods
```

**Pros**:
- ✅ Balance of simplicity and maintainability
- ✅ Validation layer (enforces critical requirement)
- ✅ Reusable helpers (DRY principle)
- ✅ Easy to test (unit test parts separately)
- ✅ No external dependencies
- ✅ Clear code structure

**Cons**:
- ❌ Some query string duplication
- ❌ Multiple classes to coordinate (acceptable trade-off)

**Complexity**: Medium  
**Time**: 2 hours

---

## 🎯 Decision

**Selected Option**: **Option 4 - Hybrid String Templates with Validator Class**

### Rationale

1. **Best Balance**: Combines simplicity of string templates with maintainability of helper classes

2. **Meets All Requirements**:
   - ✓ Parameter binding (SQL injection prevention)
   - ✓ Enforces partition predicates (validator)
   - ✓ Supports all three modes clearly
   - ✓ Adaptive window calculation (helper)
   - ✓ Testable components

3. **Development Efficiency**: 2-hour implementation is reasonable for the complexity

4. **Future-Proof**: Easy to extend with new query modes or filters

### Comparison

| Criteria | Option 1 | Option 2 | Option 3 | Option 4 ✅ |
|----------|----------|----------|----------|-------------|
| Simplicity | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ |
| Maintainability | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Testability | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Debuggability | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ |
| No Dependencies | ✅ | ✅ | ❌ | ✅ |
| Implementation Time | 1.5h | 3h | 2.5h | 2h |

---

## 🏗️ Architecture Design

### Class Structure

```python
# src/query_builder.py

class QueryValidator:
    """Validates queries meet BigQuery partition requirements."""
    
    @staticmethod
    def validate_partition_predicate(query: str) -> None:
        """Ensure query contains timestamp predicates (partition requirement)."""
        if 'timestamp >=' not in query.lower() or 'timestamp <=' not in query.lower():
            raise ValueError("Query must include timestamp range predicates")


class QueryHelpers:
    """Helper utilities for query construction."""
    
    @staticmethod
    def calculate_adaptive_window(timeframe: str, records_needed: int) -> int:
        """Calculate window in days for given timeframe and record count."""
        records_per_day = {
            '1M': 1/30, '1w': 1/7, '1d': 1,
            '4h': 6, '1h': 24, '15': 96, '5': 288, '1': 1440
        }
        rpd = records_per_day.get(timeframe, 1)
        days_needed = int((records_needed / rpd) * 1.2)  # 20% buffer
        return max(1, min(5475, days_needed))  # 1 day to 15 years
    
    @staticmethod
    def build_exchange_clause(exchange: Optional[str]) -> tuple[str, dict]:
        """Build exchange clause and parameter if provided."""
        if exchange:
            return "AND exchange = @exchange", {'exchange': exchange}
        return "", {}


class QueryBuilder:
    """Builds BigQuery SQL queries with partition enforcement."""
    
    def __init__(self, project: str, dataset: str, table: str):
        self.project = project
        self.dataset = dataset
        self.table = table
        self.validator = QueryValidator()
        self.helpers = QueryHelpers()
    
    def build_all_query(self, symbol: str, timeframe: str, 
                       exchange: Optional[str] = None) -> tuple[str, dict]:
        """Build query for ALL mode (15-year history)."""
        # Implementation...
    
    def build_range_query(self, symbol: str, timeframe: str,
                         from_time, to_time, 
                         exchange: Optional[str] = None) -> tuple[str, dict]:
        """Build query for RANGE mode (explicit timestamps)."""
        # Implementation...
    
    def build_neighborhood_query(self, symbol: str, timeframe: str,
                                center_timestamp, n_before: int, n_after: int,
                                exchange: Optional[str] = None) -> tuple[str, dict]:
        """Build query for NEIGHBORHOOD mode (adaptive window + UNION ALL)."""
        # Implementation...
```

### Component Diagram

```
┌─────────────────────────────────────────┐
│            main.py                       │
│  (CLI argument parsing & orchestration)  │
└───────────────┬─────────────────────────┘
                │ args: symbol, timeframe, mode
                ↓
┌─────────────────────────────────────────┐
│         QueryBuilder                     │
│  - build_all_query()                     │
│  - build_range_query()                   │
│  - build_neighborhood_query()            │
└────┬────────────────┬───────────────────┘
     │                │
     │ uses           │ uses
     ↓                ↓
┌────────────┐   ┌────────────────────┐
│ QueryHelpers│   │ QueryValidator      │
│ - calc window│   │ - validate partition│
│ - exchange   │   └────────────────────┘
└────────────┘
     │
     │ returns
     ↓
┌─────────────────────────────────────────┐
│  (query_string, parameters_dict)         │
│                 ↓                        │
│         BigQueryClient.execute()         │
└─────────────────────────────────────────┘
```

### Data Flow

```
User Input (CLI args)
  ↓
main.py validates & parses
  ↓
QueryBuilder.build_neighborhood_query(symbol, timeframe, center, n_before, n_after)
  ↓
QueryHelpers.calculate_adaptive_window(timeframe, max(n_before, n_after))
  ↓ returns: window_days
QueryBuilder constructs UNION ALL query string with f-strings
  ↓
QueryBuilder builds parameters dict
  ↓
QueryValidator.validate_partition_predicate(query)
  ↓ raises ValueError if invalid
QueryBuilder returns (query, params)
  ↓
BigQueryClient.execute(query, params)
  ↓
Results → OutputHandler
```

---

## 📝 Implementation Guidelines

### 1. QueryHelpers Implementation (30 min)

**Adaptive Window Calculation**:
- Use dict mapping for `records_per_day`
- Formula: `days = (records / records_per_day) * 1.2`
- Bounds: minimum 1 day, maximum 5475 days (15 years)
- Buffer: 20% to account for data gaps and non-trading days

**Exchange Clause Builder**:
- Return tuple: `(clause_string, params_dict)`
- If exchange provided: `("AND exchange = @exchange", {'exchange': value})`
- If not provided: `("", {})`

### 2. QueryValidator Implementation (15 min)

**Partition Predicate Validation**:
- Check for both `timestamp >=` and `timestamp <=`
- Case-insensitive search
- Raise `ValueError` with clear message if missing
- Called on every query before return (fail-fast)

### 3. QueryBuilder.build_all_query() (30 min)

**ALL Mode Query**:
```sql
SELECT timestamp, open, high, low, close, volume
FROM `{project}.{dataset}.{table}`
WHERE symbol = @symbol
  AND timeframe = @timeframe
  AND timestamp >= @start_time  -- 15 years ago
  AND timestamp <= @end_time    -- now
  [AND exchange = @exchange]    -- optional
ORDER BY timestamp ASC
```

**Parameters**:
- `start_time`: `datetime.now() - timedelta(days=5475)`
- `end_time`: `datetime.now()`
- `symbol`, `timeframe`, `exchange` (optional)

### 4. QueryBuilder.build_range_query() (20 min)

**RANGE Mode Query**:
- Use provided `from_time` and `to_time` directly
- Similar structure to ALL mode
- Validate `from_time <= to_time` before building query

### 5. QueryBuilder.build_neighborhood_query() (35 min)

**NEIGHBORHOOD Mode Query**:
- Calculate adaptive window using `QueryHelpers`
- Build three-part UNION ALL query:
  1. **Before**: Records before center, DESC order, LIMIT n_before
  2. **Center**: Exact center timestamp, LIMIT 1
  3. **After**: Records after center, ASC order, LIMIT n_after
- Final ORDER BY timestamp ASC to sort combined results
- Each subquery uses adaptive window to satisfy partition requirement

**UNION ALL Structure**:
```sql
(before query with window_days before center) UNION ALL
(center query) UNION ALL
(after query with window_days after center)
ORDER BY timestamp ASC
```

### 6. Unit Testing Strategy (30 min)

**Test QueryHelpers**:
- Test `calculate_adaptive_window()` with all timeframes
- Test edge cases: 1M with large N, 1m with small N
- Verify bounds (min 1, max 5475)

**Test QueryValidator**:
- Test valid query (has both predicates)
- Test invalid queries (missing one or both predicates)
- Verify exception message clarity

**Test QueryBuilder**:
- Test all three modes with sample inputs
- Verify query strings contain expected SQL
- Verify parameter dicts are correct
- Mock validator/helpers if needed

---

## ✅ Validation Against Requirements

### Functional Requirements
- [✓] Generate parameterized SQL queries
- [✓] Enforce timestamp predicates in ALL queries
- [✓] Support ALL mode (15-year range)
- [✓] Support RANGE mode (explicit timestamps)
- [✓] Support NEIGHBORHOOD mode (adaptive window + UNION ALL)
- [✓] Calculate adaptive windows based on timeframe
- [✓] Handle edge cases (validator catches invalid queries)

### Technical Constraints
- [✓] Works with `google-cloud-bigquery` client library
- [✓] Partition predicates MANDATORY (validator enforces)
- [✓] Parameterized queries (prevents SQL injection)
- [✓] Supports all timeframes ('1M' to '1')

### Quality Requirements
- [✓] Maintainable: Clear class structure, separation of concerns
- [✓] Testable: Static methods, pure functions, unit testable
- [✓] Debuggable: Query strings can be inspected/printed
- [✓] Performance: Minimal overhead (string formatting only)

---

## 📊 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Partition predicates missing | Low | High | Validator enforces on every query |
| Adaptive window too small (1M) | Low | Medium | Tested formula with 20% buffer |
| SQL injection | Low | High | Parameterized queries only |
| Query complexity (NEIGHBORHOOD) | Low | Low | Clear UNION ALL structure |
| Code duplication in queries | Medium | Low | Acceptable for readability |

---

## 🎯 Success Criteria

- [ ] All three query modes implemented
- [ ] Validator catches missing partition predicates
- [ ] Adaptive window calculation tested with all timeframes
- [ ] Unit tests passing (helpers, validator, builder)
- [ ] Integration test with mock BigQuery client
- [ ] Code reviewed for SQL injection vulnerabilities
- [ ] Documentation added to all public methods

---

## 📈 Next Steps

1. **BUILD Mode**: Implement according to this design
2. **Unit Tests**: Test each component separately
3. **Integration Test**: Test with mock BigQuery responses
4. **Code Review**: Verify partition enforcement and security
5. **Documentation**: Add docstrings and usage examples

---

## 📚 References

- BigQuery Parameterized Queries: https://cloud.google.com/bigquery/docs/parameterized-queries
- Table Partitioning Best Practices: https://cloud.google.com/bigquery/docs/querying-partitioned-tables
- Memory Bank: `/memory-bank/critical-requirements.md` (adaptive window calculations)
- Memory Bank: `/memory-bank/query-patterns.md` (query mode specifications)

