# Task BQ-004: PLAN Mode - GCS Output with Local Fallback

**Status**: ✅ PLANNING COMPLETE (Reviewed & Corrected)  
**Date**: 2025-12-12  
**Complexity**: Level 2 - Simple Enhancement  
**Estimated Duration**: 55 minutes

## ✅ Plan Review & Corrections Applied

**Review Date**: 2025-12-12  
**Reviewer**: AI Assistant  
**Status**: All critical issues resolved

### Critical Corrections Made:
1. ✅ **Fixed `--output` flag logic** (Section 2.4) - Changed to `default=None` in argparse
2. ✅ **Added GCS exceptions** (Section 4) - `GCSUploadError` and `GCSAuthenticationError`
3. ✅ **Clarified temp file handling** (Section 2.3) - Explicit cleanup logic with `tempfile`
4. ✅ **Added `get_request_id()` import** (Section 2.3) - From `src.logger`
5. ✅ **Enhanced Phase 1** (Section 6) - Added exceptions.py and argparse updates
6. ✅ **Enhanced all phases** (Section 6) - More detailed step-by-step instructions
7. ✅ **Updated file list** (Section 9) - Now includes `src/exceptions.py`

**Plan Quality**: 10/10 ⭐ Ready for implementation

---

## 1. Task Clarification & Requirements

### User Request (Russian → English Translation)
"Currently, JSON files are saved to the project folder. This variant should be preserved (if run with the --output flag), but by default, they should be saved to Google Cloud Storage bucket.

Cloud Storage data (bucket ID, etc.) goes to `.env` file. Also, the path to the service account key file (separate service account, not the one used for BigQuery).

The JSON file saved to the bucket gets the name `request_id` and the `.json` extension.

The query result should form a download link via HTTP as described in the GCS documentation.

On the GCP side, `allUsers` already has `Storage Object Viewer` permission."

### Clarified Requirements

#### 1. Default Behavior (No --output flag)
- Save JSON file to Google Cloud Storage bucket
- Filename: `{request_id}.json` (using the existing request_id from logger)
- Return publicly accessible HTTP download URL
- Log the URL for user reference

#### 2. Fallback Behavior (With --output flag)
- Save JSON file to local filesystem
- Use existing filename format: `{symbol}_{timeframe}_{timestamp}.json`
- Behave as current implementation
- No GCS upload needed

#### 3. Configuration
- Add to `.env` file:
  - `GCS_BUCKET_NAME`: Name of the GCS bucket
  - `GCS_SERVICE_ACCOUNT_KEY`: Path to separate service account JSON key
- Optional: If not configured, can fall back to local-only mode
- Service account must have `Storage Object Creator` and `Storage Object Viewer` roles

#### 4. Download Link Generation
- Format: Standard GCS HTTP access pattern
- Reference: [GCS Access Documentation](https://docs.cloud.google.com/storage/docs/access-public-data)
- Since `allUsers` has `Storage Object Viewer` permission, URL format:
  - `https://storage.googleapis.com/{bucket_name}/{object_name}`
  - Alternative: `https://console.cloud.google.com/storage/browser/_details/{bucket_name}/{object_name}`

---

## 2. Component Breakdown

### 2.1 Configuration Module (`src/config.py`)
**Changes Required**:
- Add optional GCS configuration variables
- Load `GCS_BUCKET_NAME` (string)
- Load `GCS_SERVICE_ACCOUNT_KEY` (path)
- Add validation: If GCS enabled, verify bucket name and key path exist

**Implementation Details**:
```python
# Add to Config dataclass:
gcs_bucket_name: Optional[str] = None
gcs_service_account_key_path: Optional[Path] = None

# Add property (replaces validate_gcs_config method):
@property
def gcs_enabled(self) -> bool:
    """Check if GCS is properly configured and available."""
    return (
        self.gcs_bucket_name is not None 
        and self.gcs_bucket_name.strip() != ""
        and self.gcs_service_account_key_path is not None
        and self.gcs_service_account_key_path.exists()
    )
```

**Dependencies**: None (uses existing pattern)  
**Risk**: Low (optional feature, no breaking changes)

---

### 2.2 GCS Handler Component (`src/gcs_handler.py`)
**Purpose**: Encapsulate Google Cloud Storage operations  
**Status**: New file

**Class: GCSHandler**
```python
class GCSHandler:
    """Handles uploads to Google Cloud Storage bucket."""
    
    def __init__(self, bucket_name: str, credentials_path: Path, logger: Logger):
        """Initialize GCS client with service account credentials."""
        # Initialize storage client with JSON key
        # Set bucket reference
    
    def upload_file(self, local_file_path: Path, object_name: str) -> str:
        """Upload local file to GCS bucket.
        
        Args:
            local_file_path: Path to local file to upload
            object_name: Name for object in bucket (usually request_id.json)
        
        Returns:
            Public download URL for the uploaded file
        
        Raises:
            GCSUploadError: If upload fails
        """
        # Validate inputs
        # Upload file with Content-Type: application/json
        # Generate and return download URL
        # Log success with structured logging
    
    def generate_download_url(self, object_name: str) -> str:
        """Generate publicly accessible download URL.
        
        Format: https://storage.googleapis.com/{bucket}/{object}
        """
        # Construct URL from bucket name and object name
        # Return formatted URL
```

**Error Handling**:
- Catch authentication errors → AuthenticationError
- Catch bucket not found → ValidationError
- Catch permission errors → FileSystemError
- Catch network errors → Retryable errors (use backoff)

**Dependencies**:
- `google.cloud.storage` (version 2.10.0+)
- Uses existing exception hierarchy

**Risk**: 
- Authentication with separate service account
- Mitigation: Validate credentials on initialization
- Mitigation: Test with real bucket before production

---

### 2.3 Output Handler Enhancement (`src/output_handler.py`)
**Purpose**: Support both local and GCS output  
**Status**: Modification (existing component)

**Changes**:
1. Add optional parameters to `__init__`:
   ```python
   def __init__(self, logger: Logger, gcs_handler: Optional[GCSHandler] = None):
       self.logger = logger
       self.gcs_handler = gcs_handler
   ```

2. Modify `save_to_file()` method:
   ```python
   def save_to_file(
       self,
       data: List[Dict],
       output_path: Path,
       symbol: str,
       timeframe: str,
       metadata: Optional[Dict] = None,
       use_gcs: bool = True,  # New parameter
   ) -> Tuple[Path, Optional[str]]:  # Returns (local_path, gcs_url)
       """Save to GCS by default, or to local filesystem.
       
       Args:
           use_gcs: If True and gcs_handler available, upload to GCS
       
       Returns:
           Tuple of (local_path, gcs_download_url or None)
       """
   ```

3. Implementation logic:
   ```python
   from .logger import get_request_id  # Add this import
   import tempfile
   
   # In save_to_file():
   request_id = get_request_id() or "unknown"
   
   if use_gcs and self.gcs_handler:
       # Save to temporary file
       temp_dir = Path(tempfile.gettempdir())
       temp_path = temp_dir / f"{request_id}.json"
       # ... write JSON to temp_path ...
       
       # Upload to GCS
       object_name = f"{request_id}.json"
       gcs_url = self.gcs_handler.upload_file(temp_path, object_name)
       
       # Clean up temporary file after successful upload
       temp_path.unlink()
       
       return temp_path, gcs_url
   else:
       # Save to specified output_path with existing filename format
       final_path = output_path / self.generate_filename(symbol, timeframe, start_timestamp)
       # ... write JSON to final_path ...
       return final_path, None
   ```

4. Return values:
   - `file_path`: Path to local file
   - `gcs_url`: GCS download URL if uploaded, else None

**Backward Compatibility**:
- Default behavior: Try GCS if handler provided, otherwise local
- `--output` flag forces local storage
- Existing code works unchanged

**Risk**: Low (additive parameter, existing code unaffected)

---

### 2.4 Main Entry Point (`main.py`)
**Purpose**: Orchestrate storage selection and output  
**Status**: Modification (existing component)

**Changes**:
1. Load GCS configuration:
   ```python
   # After loading BQ config
   gcs_handler = None
   if config.gcs_enabled:
       try:
           gcs_handler = GCSHandler(
               bucket_name=config.gcs_bucket_name,
               credentials_path=config.gcs_service_account_key_path,
               logger=logger
           )
       except Exception as exc:
           # Log warning, continue with local-only
           log_struct(logger, "WARNING", "GCS unavailable, using local storage only")
           gcs_handler = None
   ```

2. Initialize OutputHandler with GCS:
   ```python
   output_handler = OutputHandler(logger, gcs_handler=gcs_handler)
   ```

3. Determine storage destination:
   ```python
   # Logic: If --output is None (not provided), use GCS
   # If --output is provided (any path including '.'), use local
   use_gcs = args.output is None and gcs_handler is not None
   ```
   
   **IMPORTANT**: Update argparse `--output` to have `default=None` instead of `default='.'`:
   ```python
   parser.add_argument(
       '--output', '-o',
       default=None,  # Changed from '.'
       help='Output directory (if not specified, uploads to GCS)'
   )
   ```

4. Call save_to_file:
   ```python
   file_path, gcs_url = output_handler.save_to_file(
       data,
       output_path,
       symbol,
       timeframe,
       metadata=metadata,
       use_gcs=use_gcs,
   )
   ```

5. Update success message:
   ```python
   if gcs_url:
       print(f"File saved to GCS: {gcs_url}")
   else:
       print(f"File saved locally: {file_path}")
   ```

**Risk**: Low (configuration-driven, graceful fallback)

---

### 2.5 Environment Configuration (`env.example`)
**Changes**:
```bash
# Existing BigQuery config...

# Google Cloud Storage Configuration (optional)
GCS_BUCKET_NAME=your-bucket-name
GCS_SERVICE_ACCOUNT_KEY=/path/to/gcs-service-account-key.json

# To save to local filesystem instead of GCS, use --output flag:
# python main.py --symbol BTCUSDT --timeframe 1d --all --output ./local-output
```

**Documentation**:
- Add comment explaining GCS is default
- Explain `--output` flag for local fallback
- Show that separate service account is required
- Note about permissions requirement

---

## 3. Configuration & Dependencies

### 3.1 Configuration Schema
```python
# In .env:
GCS_BUCKET_NAME=my-market-data-bucket
GCS_SERVICE_ACCOUNT_KEY=/path/to/gcs-key.json

# Both must be present for GCS to be enabled
# If either is missing, falls back to local storage
```

### 3.2 Dependencies
**New Dependency**:
- `google-cloud-storage>=2.10.0`

**Installation**:
```bash
pip install google-cloud-storage>=2.10.0
```

**Update `requirements.txt`**:
- Already has `google-cloud-bigquery`
- Add `google-cloud-storage>=2.10.0`

**Risk**: 
- No additional risk (same publisher as BigQuery client)
- Version selection: 2.10.0+ is stable and well-tested

---

## 4. Error Handling Strategy

### GCS-Specific Errors
**Add to `src/exceptions.py`:**
```python
class GCSUploadError(BQExtractorError):
    """Error during GCS upload operation.
    
    Exit code: 5
    Retryable: Yes (network issues)
    """
    DEFAULT_EXIT_CODE = 5
    DEFAULT_RETRYABLE = True  # Network failures can be retried
    

class GCSAuthenticationError(BQExtractorError):
    """GCS authentication/authorization failure.
    
    Exit code: 6
    Retryable: No (requires credential fix)
    """
    DEFAULT_EXIT_CODE = 6
    DEFAULT_RETRYABLE = False
```

### Error Scenarios
1. **GCS Bucket not found**: Validation → Fallback to local
2. **GCS Credentials invalid**: Log warning → Use local storage
3. **GCS Upload network failure**: Backoff retry (decorated method)
4. **Permission denied**: GCSAuthenticationError with guidance
5. **Local filesystem unavailable**: FileSystemError (existing)

### Graceful Degradation
- If GCS unavailable: Warn and use local storage
- If local also unavailable: Fail with clear error
- Never lose data due to GCS issues
- Always provide option to use local storage

---

## 5. Testing Strategy

### Unit Tests (Optional, Time Permitting)
1. **Config loading**:
   - Load GCS config when present
   - Handle missing GCS config (optional)
   - Validate bucket name format

2. **GCSHandler**:
   - Mock `google.cloud.storage.Bucket`
   - Test successful upload
   - Test URL generation
   - Test error handling

3. **OutputHandler**:
   - Test with GCS handler (mock)
   - Test with local storage
   - Test with --output flag
   - Verify conditional logic

4. **Integration**:
   - Mock GCS operations
   - Verify main.py orchestration
   - Test both storage paths

### Manual Testing (Required)
1. **Setup**:
   - Create test GCS bucket
   - Create separate service account with appropriate roles
   - Update .env with real credentials

2. **Test Cases**:
   - Default run (no --output): Verify file in GCS bucket
   - With --output flag: Verify file in local directory
   - Check download URL is accessible
   - Verify request_id in filename

3. **Edge Cases**:
   - Run with invalid GCS credentials → Graceful fallback
   - Run with GCS_BUCKET_NAME but missing key → Validation error
   - Network timeout during upload → Backoff retry

---

## 6. Implementation Sequence

### Phase 1: Configuration (10 min)
1. Update `src/config.py`:
   - Add `gcs_bucket_name: Optional[str] = None`
   - Add `gcs_service_account_key_path: Optional[Path] = None`
   - Add property `gcs_enabled` with full validation
2. Update `src/exceptions.py`:
   - Add `GCSUploadError` class (exit_code=5, retryable=True)
   - Add `GCSAuthenticationError` class (exit_code=6, retryable=False)
3. Update `env.example` with GCS variables and documentation
4. Update `main.py` argparse:
   - Change `--output` default from `'.'` to `None`

### Phase 2: GCS Handler (15 min)
1. Create `src/gcs_handler.py`:
   - Import: `from google.cloud import storage`
   - Import: `from google.cloud.exceptions import GoogleCloudError`
2. Implement `GCSHandler` class:
   - `__init__()` with credentials validation and client initialization
   - `upload_file()` with structured logging and error handling
   - `generate_download_url()` using format: `https://storage.googleapis.com/{bucket}/{object}`
3. Add comprehensive error handling:
   - Catch `GoogleCloudError` → map to `GCSUploadError`
   - Catch permission errors → `GCSAuthenticationError`
   - Use structured logging for all operations

### Phase 3: Output Handler (10 min)
1. Modify `src/output_handler.py`:
   - Add import: `from .logger import get_request_id`
   - Add import: `import tempfile`
   - Add `gcs_handler` parameter to `__init__()`
   - Add `use_gcs` parameter to `save_to_file()`
   - Change return type: `-> Tuple[Path, Optional[str]]`
2. Implement conditional logic:
   - If `use_gcs=True`: Save to temp file, upload to GCS, cleanup temp file
   - If `use_gcs=False`: Save to output_path with existing filename format
3. Return dual values: `(file_path, gcs_url or None)`

### Phase 4: Main Entry (10 min)
1. Update `main.py`:
   - Import `GCSHandler` from `src.gcs_handler`
   - **CRITICAL**: Verify argparse `--output` has `default=None`
2. Initialize GCS handler with try/except (after config load):
   - Check `config.gcs_enabled`
   - Create `GCSHandler` instance
   - Catch exceptions and log warning, set `gcs_handler = None`
3. Pass GCS handler to OutputHandler initialization
4. Determine storage destination:
   - `use_gcs = args.output is None and gcs_handler is not None`
5. Update `save_to_file()` call with `use_gcs` parameter
6. Handle dual return: `file_path, gcs_url = output_handler.save_to_file(...)`
7. Update success message:
   - If `gcs_url`: Print GCS URL
   - Else: Print local file path

### Phase 5: Finalization (10 min)
1. Update `requirements.txt`:
   - Add `google-cloud-storage>=2.10.0`
2. Update `README.md`:
   - Add "Google Cloud Storage Output" section
   - Document GCS configuration (bucket name, service account key)
   - Explain default behavior (GCS) vs. `--output` flag (local)
   - Add examples for both storage modes
   - Document download URL format
3. Manual testing with real GCS bucket:
   - Test default mode (no --output) → Verify file in GCS
   - Test local mode (with --output) → Verify file locally
   - Verify download URL is accessible
   - Test graceful fallback scenarios

**Total Estimated Time**: 55 minutes (includes testing)

---

## 7. Success Criteria

- [ ] JSON files save to GCS bucket by default
- [ ] Filename in bucket: `{request_id}.json`
- [ ] Download URL generated and logged
- [ ] --output flag saves to local filesystem
- [ ] Existing filename format for local saves: `{symbol}_{timeframe}_{timestamp}.json`
- [ ] Graceful fallback if GCS unavailable
- [ ] No linter errors
- [ ] All existing tests pass
- [ ] README updated with GCS documentation
- [ ] Fully backward compatible
- [ ] Manual testing with real GCS bucket successful

---

## 8. Risk Assessment & Mitigation

### Risk: GCS Credential Issues
**Severity**: Medium  
**Mitigation**:
- Validate credentials on initialization
- Clear error messages guide user
- Graceful fallback to local storage
- Document credential setup in README

### Risk: Breaking Existing Tests
**Severity**: Low  
**Mitigation**:
- GCS is optional (no breaking changes)
- Existing tests use local storage by default
- Mock GCS handler in tests
- Backward compatibility maintained

### Risk: Dependencies Version Conflict
**Severity**: Low  
**Mitigation**:
- Use compatible versions (2.10.0+)
- Same publisher as existing google-cloud-bigquery
- Explicitly pin version in requirements.txt
- Test with current environment

### Risk: Default Behavior Change
**Severity**: Medium  
**Mitigation**:
- Clearly document default is GCS (if configured)
- Make --output flag behavior explicit
- Provide clear success messages showing where file went
- Add examples to README

---

## 9. Detailed Changes Summary

### Files to Modify
1. **src/config.py** - Add GCS configuration (fields + property)
2. **src/exceptions.py** - Add GCSUploadError and GCSAuthenticationError
3. **src/output_handler.py** - Add dual-storage support with imports
4. **main.py** - Initialize GCS, fix argparse default, route output
5. **env.example** - Document GCS configuration
6. **requirements.txt** - Add google-cloud-storage>=2.10.0
7. **README.md** - Document GCS usage with examples

### Files to Create
1. **src/gcs_handler.py** - New GCS operations utility (complete implementation)

---

## 10. Implementation Notes

### Design Principles
1. **Separation of Concerns**: GCSHandler isolated in separate module
2. **Optional Integration**: GCS is optional, no forced dependency on credentials
3. **Backward Compatibility**: Existing code paths unchanged
4. **Consistent Patterns**: Follow existing error handling, logging, configuration
5. **Graceful Degradation**: Fall back to local storage if GCS unavailable

### Key Decisions
1. **Request ID for GCS filename**: Already generated by logger, reuse it
2. **Dual file save**: Save to temporary local file, upload to GCS if needed
3. **Service account separation**: Use different account for GCS (as required)
4. **URL format**: Simple HTTP URL (bucket is public with allUsers permission)
5. **Backward compatibility**: --output flag determines storage destination

### Code Quality
- Follow existing code style
- Use type hints
- Add docstrings
- Maintain logging consistency
- No linting errors

---

## Summary

This is a **Level 2 - Simple Enhancement** task focused on adding GCS output capability as the default storage destination, with local filesystem as an optional fallback. The implementation is straightforward, follows established patterns, and maintains full backward compatibility.

**Key Factors**:
- Limited scope (1 new file, 4 code modifications, 3 doc updates)
- No complex architectural decisions
- Graceful degradation and error handling
- Clear implementation path
- Estimated 55 minutes total

**Implementation Readiness Checklist**:
- ✅ All requirements clarified and translated
- ✅ Component architecture defined
- ✅ Error handling strategy complete
- ✅ Testing strategy documented
- ✅ All 5 phases detailed with specific tasks
- ✅ Risk assessment with mitigations
- ✅ Backward compatibility ensured
- ✅ Critical logic errors corrected

**Next Phase**: BUILD mode - Begin implementation with Phase 1 (Configuration)

