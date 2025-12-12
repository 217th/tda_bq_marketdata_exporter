# Implementation Plan: BQ-002 - Add Request ID to Logs

## Task Overview
**Goal**: Add unique request ID to all log records during extraction execution

**Complexity**: Level 2 - Simple Enhancement  
**Estimated Time**: 1-2 hours  
**Mode Sequence**: VAN → PLAN → BUILD → REFLECT

## Requirements

### Functional Requirements
1. Generate unique request ID at the start of each extraction request
2. Include request_id in ALL log messages throughout the request lifecycle
3. Request ID format: UUID4 (standard Python uuid module)
4. Request ID should appear in structured log output as a label

### Non-Functional Requirements
1. Minimal code changes (leverage existing logging infrastructure)
2. No breaking changes to existing functionality
3. Thread-safe (if script ever becomes multi-threaded)
4. Easy to trace requests across log aggregation systems

## Implementation Approach

### Solution Design
Use Python's `contextvars` module to propagate request ID through the call stack without modifying function signatures. This is the cleanest approach for context propagation.

**Key Components**:
1. **Context Variable**: Create `request_id` context variable in logger module
2. **ID Generation**: Generate UUID4 at main() entry point
3. **Automatic Inclusion**: Modify `StructuredFormatter` to automatically include request_id from context
4. **Backward Compatible**: If no request_id in context, logs work normally

### Alternative Approaches Considered
- ❌ **Thread-local storage**: Less modern than contextvars
- ❌ **Function parameter threading**: Requires changing all function signatures
- ❌ **Logger adapter**: More complex, less flexible
- ✅ **Context variables**: Clean, modern, minimal changes

## Implementation Plan

### Phase 1: Logger Module Updates (30 min)

**File**: `src/logger.py`

**Changes**:
1. Import `contextvars` and `uuid` modules
2. Create context variable: `request_id_var = contextvars.ContextVar('request_id', default=None)`
3. Add utility function: `set_request_id(request_id: str)` to set context
4. Add utility function: `get_request_id() -> Optional[str]` to retrieve context
5. Modify `StructuredFormatter.format()`:
   - Check for request_id in context
   - If present, add to log_data as `request_id` field
6. Add docstrings for new functions

**Verification**:
- Unit test: Generate request ID and verify it appears in logs
- Unit test: Verify logs work without request ID (backward compatibility)

### Phase 2: Main Entry Point Integration (15 min)

**File**: `main.py`

**Changes**:
1. Import `uuid` and `set_request_id` from logger module
2. In `main()` function, after argument parsing:
   - Generate UUID: `request_id = str(uuid.uuid4())`
   - Set context: `set_request_id(request_id)`
   - Log startup message with request_id already in context
3. Update initial log message to confirm request tracking started

**Verification**:
- Manual test: Run extraction and verify request_id in all logs
- Verify request_id is consistent across all log entries for single run

### Phase 3: Testing & Verification (15 min)

**Tasks**:
1. Write unit tests for new logger functions:
   - `test_request_id_context_setting`
   - `test_request_id_in_log_output`
   - `test_logs_without_request_id` (backward compatibility)
2. Integration test: Run full extraction and verify request_id propagation
3. Test scenarios:
   - Normal extraction (ALL mode)
   - Error scenarios (authentication failure, validation error)
   - Verify request_id present in error logs

**Test Files**:
- `tests/test_logger.py` (add new tests)
- Manual integration test with real BigQuery

### Phase 4: Documentation (15 min)

**Updates Required**:
1. **README.md**: Add section on request ID tracking in logs
2. **Code comments**: Document contextvars usage
3. **Example log output**: Show request_id in sample log messages

## Technical Details

### Context Variables API
```python
import contextvars

# Define context variable
request_id_var = contextvars.ContextVar('request_id', default=None)

# Set value (in main.py)
request_id_var.set("123e4567-e89b-12d3-a456-426614174000")

# Get value (in StructuredFormatter)
request_id = request_id_var.get()  # Returns None if not set
```

### Expected Log Output Format
```json
{
  "timestamp": "2025-12-12T10:30:00.123456Z",
  "level": "INFO",
  "logger": "bq-stock-extractor",
  "message": "Executing BigQuery query",
  "request_id": "123e4567-e89b-12d3-a456-426614174000",
  "labels": {
    "service": "bq-stock-extractor",
    "environment": "development",
    "symbol": "BTCUSDT",
    "timeframe": "1d"
  },
  "fields": {
    "query_length": 1234
  }
}
```

## Implementation Checklist

### Phase 1: Logger Module
- [ ] Import contextvars and uuid
- [ ] Define request_id_var context variable
- [ ] Implement set_request_id() function
- [ ] Implement get_request_id() function
- [ ] Modify StructuredFormatter to include request_id
- [ ] Add docstrings
- [ ] Write unit tests

### Phase 2: Main Integration
- [ ] Import uuid and set_request_id in main.py
- [ ] Generate UUID in main()
- [ ] Set request_id context at start
- [ ] Verify in manual test

### Phase 3: Testing
- [ ] Unit tests for context functions
- [ ] Unit tests for formatter with request_id
- [ ] Integration test with full extraction
- [ ] Test error scenarios

### Phase 4: Documentation
- [ ] Update README with request tracking info
- [ ] Add code comments
- [ ] Document example log output

## Success Criteria
- ✅ Every log message during extraction includes request_id
- ✅ Request ID is unique per execution
- ✅ Request ID is consistent across all logs in single execution
- ✅ Backward compatible (logs work if request_id not set)
- ✅ All tests passing
- ✅ Documentation updated

## Risk Assessment

### Low Risk
- **Reason**: Additive change, no modification to existing logic
- **Mitigation**: Comprehensive testing, backward compatibility

### Potential Issues
1. **Context not propagating**: Unlikely with synchronous code
2. **Performance impact**: Negligible (single UUID generation + context lookup)
3. **Breaking existing tests**: May need to update test assertions

## Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Logger Module | 30 min | 30 min |
| Phase 2: Main Integration | 15 min | 45 min |
| Phase 3: Testing | 15 min | 60 min |
| Phase 4: Documentation | 15 min | 75 min |

**Total Estimated Time**: 1 hour 15 minutes

## Next Steps
1. ✅ VAN mode complete
2. ✅ PLAN mode complete
3. ⏭️ **Proceed to BUILD mode** - Implement changes
4. Testing & verification
5. REFLECT mode - Review implementation

**Ready to implement!**

