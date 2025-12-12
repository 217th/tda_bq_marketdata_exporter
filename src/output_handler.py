"""
Output handler for BigQuery query results.

Transforms BigQuery results to JSON format and saves to file.
Output file naming: {symbol}_{timeframe}_{start_timestamp}.json
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from .exceptions import FileSystemError


class OutputHandler:
    """Handles output formatting and file writing."""
    
    # Fields to include in output (in order)
    CANDLE_FIELDS = ["date", "open", "high", "low", "close", "volume"]
    
    def __init__(self, logger: logging.Logger):
        """Initialize output handler.
        
        Args:
            logger: Logger instance for structured logging
        """
        self.logger = logger
    
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
    
    def generate_filename(
        self,
        symbol: str,
        timeframe: str,
        start_timestamp: datetime,
    ) -> str:
        """Generate output filename.
        
        Format: {symbol}_{timeframe}_{start_timestamp}.json
        
        Args:
            symbol: Stock symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe identifier (e.g., '1d', '15')
            start_timestamp: Start timestamp of the data
        
        Returns:
            Filename string
        
        Example:
            >>> handler.generate_filename('BTCUSDT', '1d', datetime(2024, 1, 1))
            'BTCUSDT_1d_20240101_000000.json'
        """
        timestamp_str = start_timestamp.strftime("%Y%m%d_%H%M%S")
        return f"{symbol}_{timeframe}_{timestamp_str}.json"
    
    def save_to_file(
        self,
        data: List[Dict[str, Any]],
        output_path: Path,
        symbol: str,
        timeframe: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Save transformed data to JSON file with optional metadata.
        
        Args:
            data: Transformed data to save
            output_path: Output directory path
            symbol: Stock symbol (for filename)
            timeframe: Timeframe (for filename)
            metadata: Optional metadata dictionary to include in output
        
        Returns:
            Path to the saved file
        
        Raises:
            FileSystemError: If file cannot be written
        
        Example:
            >>> handler = OutputHandler(logger)
            >>> data = [{"date": "2024-01-01T00:00:00Z", "open": 100, ...}]
            >>> metadata = {"request_id": "123", "symbol": "BTCUSDT", ...}
            >>> file_path = handler.save_to_file(data, Path("."), "BTCUSDT", "1d", metadata)
        """
        try:
            # Ensure output directory exists
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Determine start timestamp from data
            if data:
                # Parse date from first record
                first_date_str = data[0]["date"]
                try:
                    start_timestamp = datetime.strptime(
                        first_date_str,
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                except ValueError:
                    # Fallback to current time if parsing fails
                    start_timestamp = datetime.utcnow()
            else:
                # No data, use current time
                start_timestamp = datetime.utcnow()
            
            # Generate filename
            filename = self.generate_filename(symbol, timeframe, start_timestamp)
            file_path = output_path / filename
            
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
            
            # Write JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            self.logger.info(
                f"Output file saved: {file_path}",
                extra={
                    "labels": {
                        "symbol": symbol,
                        "timeframe": timeframe,
                    },
                    "fields": {
                        "file_path": str(file_path),
                        "record_count": len(data),
                        "file_size_bytes": file_path.stat().st_size,
                        "has_metadata": metadata is not None,
                    },
                }
            )
            
            return file_path
            
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

