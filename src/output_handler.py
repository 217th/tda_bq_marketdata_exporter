"""
Output handler for BigQuery query results.

Transforms BigQuery results to JSON format and saves to file or GCS.
Output file naming: {request_id}.json (both local and GCS)
"""

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

from .exceptions import FileSystemError
from .logger import get_request_id

if TYPE_CHECKING:
    from .gcs_handler import GCSHandler


class OutputHandler:
    """Handles output formatting and file writing (local or GCS)."""
    
    # Fields to include in output (in order)
    CANDLE_FIELDS = ["date", "open", "high", "low", "close", "volume"]
    
    def __init__(self, logger: logging.Logger, gcs_handler: Optional['GCSHandler'] = None):
        """Initialize output handler.
        
        Args:
            logger: Logger instance for structured logging
            gcs_handler: Optional GCS handler for cloud storage uploads
        """
        self.logger = logger
        self.gcs_handler = gcs_handler
    
    def transform_results(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform BigQuery results to output format.
        
        Converts timestamp field to ISO format string and ensures
        only specified candle fields are included.
        
        Args:
            rows: Raw BigQuery result rows
        
        Returns:
            Transformed rows with candle fields
        
        Example:
            >>> handler = OutputHandler(logger)
            >>> rows = [{"timestamp": datetime(...), "open": 100, ...}]
            >>> transformed = handler.transform_results(rows)
            >>> transformed[0]["date"]
            "2024-01-01T00:00:00Z"
        """
        transformed = []
        
        for row in rows:
            # Convert timestamp to ISO format string
            timestamp = row.get("timestamp")
            if isinstance(timestamp, datetime):
                date_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                date_str = str(timestamp)
            
            # Build output record with only candle fields
            record = {
                "date": date_str,
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
            }
            
            transformed.append(record)
        
        return transformed
    
    
    def save_to_file(
        self,
        data: List[Dict[str, Any]],
        output_path: Path,
        symbol: str,
        timeframe: str,
        metadata: Optional[Dict[str, Any]] = None,
        use_gcs: bool = True,
    ) -> Tuple[Path, Optional[str]]:
        """Save transformed data to JSON file (local or GCS) with optional metadata.
        
        Args:
            data: Transformed data to save
            output_path: Output directory path (used for local saves)
            symbol: Stock symbol (for filename in local mode)
            timeframe: Timeframe (for filename in local mode)
            metadata: Optional metadata dictionary to include in output
            use_gcs: If True and gcs_handler available, upload to GCS (default: True)
        
        Returns:
            Tuple of (local_file_path, gcs_download_url or None)
            - local_file_path: Path to saved file
            - gcs_download_url: Public URL if uploaded to GCS, None otherwise
        
        Raises:
            FileSystemError: If file cannot be written
            GCSUploadError: If GCS upload fails (raised by GCSHandler)
        
        Example (GCS mode):
            >>> handler = OutputHandler(logger, gcs_handler)
            >>> data = [{"date": "2024-01-01T00:00:00Z", "open": 100, ...}]
            >>> metadata = {"request_id": "abc-123", ...}
            >>> file_path, gcs_url = handler.save_to_file(data, Path("."), "BTCUSDT", "1d", metadata, use_gcs=True)
            >>> print(gcs_url)
            https://storage.googleapis.com/my-bucket/abc-123.json
        
        Example (Local mode):
            >>> handler = OutputHandler(logger)
            >>> file_path, gcs_url = handler.save_to_file(data, Path("./output"), "BTCUSDT", "1d", metadata, use_gcs=False)
            >>> print(file_path)
            ./output/abc-123.json
            >>> print(gcs_url)
            None
        """
        try:
            # Get request ID for filename (used in both GCS and local modes)
            request_id = get_request_id() or "unknown"
            filename = f"{request_id}.json"
            
            # Prepare output structure
            if metadata:
                # With metadata: wrap data in structure
                output = {
                    "metadata": metadata,
                    "data": data
                }
            else:
                # Without metadata: just the data array (backward compatible)
                output = data
            
            # Decision point: GCS or local storage?
            if use_gcs and self.gcs_handler:
                # Mode 1: Upload to GCS
                # Save to temporary file first
                temp_dir = Path(tempfile.gettempdir())
                temp_path = temp_dir / filename
                
                # Write JSON to temp file
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)
                
                self.logger.info(
                    f"Temporary file created: {temp_path}",
                    extra={
                        "labels": {
                            "symbol": symbol,
                            "timeframe": timeframe,
                        },
                        "fields": {
                            "temp_path": str(temp_path),
                            "filename": filename,
                            "record_count": len(data),
                            "file_size_bytes": temp_path.stat().st_size,
                        },
                    }
                )
                
                # Upload to GCS
                gcs_url = self.gcs_handler.upload_file(temp_path, filename)
                
                # Clean up temporary file after successful upload
                temp_path.unlink()
                
                self.logger.info(
                    f"File uploaded to GCS and temp file cleaned up",
                    extra={
                        "labels": {
                            "symbol": symbol,
                            "timeframe": timeframe,
                        },
                        "fields": {
                            "gcs_url": gcs_url,
                            "filename": filename,
                            "record_count": len(data),
                        },
                    }
                )
                
                return temp_path, gcs_url
            
            else:
                # Mode 2: Save to local filesystem
                # Ensure output directory exists
                if output_path:
                    output_path.mkdir(parents=True, exist_ok=True)
                else:
                    # Fallback to current directory
                    output_path = Path('.')
                
                # Use same filename for local storage
                file_path = output_path / filename
                
                # Write JSON file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)
                
                self.logger.info(
                    f"Output file saved locally: {file_path}",
                    extra={
                        "labels": {
                            "symbol": symbol,
                            "timeframe": timeframe,
                        },
                        "fields": {
                            "file_path": str(file_path),
                            "filename": filename,
                            "record_count": len(data),
                            "file_size_bytes": file_path.stat().st_size,
                            "has_metadata": metadata is not None,
                        },
                    }
                )
                
                return file_path, None
            
        except PermissionError as exc:
            raise FileSystemError(
                f"Permission denied writing to {output_path}: {exc}",
                context={
                    "output_path": str(output_path),
                    "symbol": symbol,
                    "timeframe": timeframe,
                }
            )
        except OSError as exc:
            raise FileSystemError(
                f"Filesystem error writing output file: {exc}",
                context={
                    "output_path": str(output_path),
                    "symbol": symbol,
                    "timeframe": timeframe,
                }
            )

