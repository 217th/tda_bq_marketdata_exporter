#!/usr/bin/env python3
"""
BigQuery Stock Quotes Extractor - Main CLI Entry Point

Python 3.13 script for extracting historical stock quotes from Google BigQuery.
Supports three query modes: ALL, RANGE, NEIGHBORHOOD.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.config import load_config
from src.logger import build_logger, log_struct, set_request_id, get_request_id
from src.query_builder import QueryBuilder
from src.bigquery_client import BigQueryClient
from src.output_handler import OutputHandler
from src.query_helpers import validate_symbol_format, validate_timeframe
from src.exceptions import BQExtractorError, ValidationError, DataNotFoundError


def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO timestamp string.
    
    Args:
        ts_str: ISO format timestamp (e.g., '2024-01-01T00:00:00Z')
    
    Returns:
        Parsed datetime object
    
    Raises:
        ValidationError: If timestamp format is invalid
    """
    try:
        # Try parsing with Z suffix
        if ts_str.endswith('Z'):
            return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
        # Try parsing without Z
        return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ValidationError(
            f"Invalid timestamp format: {ts_str}. Expected ISO format: YYYY-MM-DDTHH:MM:SSZ",
            context={"timestamp": ts_str}
        )


def parse_args():
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Extract historical stock quotes from Google BigQuery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query all data (15 years)
  python main.py --symbol BTCUSDT --timeframe 1d --all

  # Query time range
  python main.py --symbol ETHUSDT --timeframe 1h \\
    --from 2024-01-01T00:00:00Z --to 2024-12-31T23:59:59Z

  # Query neighborhood (100 records before/after timestamp)
  python main.py --symbol BTCUSDT --timeframe 15 \\
    --timestamp 2024-06-15T12:00:00Z --n-before 100 --n-after 100
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--symbol', '-s',
        required=True,
        help='Stock symbol (e.g., BTCUSDT, ETHUSDT)'
    )
    parser.add_argument(
        '--timeframe', '-t',
        required=True,
        choices=['1M', '1w', '1d', '4h', '1h', '15', '5', '1'],
        help='Timeframe identifier'
    )
    
    # Optional arguments
    parser.add_argument(
        '--exchange', '-e',
        help='Exchange identifier (optional, e.g., BINANCE)'
    )
    parser.add_argument(
        '--output', '-o',
        default='.',
        help='Output directory (default: current directory)'
    )
    
    # Query mode: ALL
    parser.add_argument(
        '--all',
        action='store_true',
        help='Query all historical data (15 years)'
    )
    
    # Query mode: RANGE
    parser.add_argument(
        '--from',
        dest='from_timestamp',
        help='Start timestamp for range query (ISO format: YYYY-MM-DDTHH:MM:SSZ)'
    )
    parser.add_argument(
        '--to',
        dest='to_timestamp',
        help='End timestamp for range query (ISO format: YYYY-MM-DDTHH:MM:SSZ)'
    )
    
    # Query mode: NEIGHBORHOOD
    parser.add_argument(
        '--timestamp',
        dest='center_timestamp',
        help='Center timestamp for neighborhood query (ISO format: YYYY-MM-DDTHH:MM:SSZ)'
    )
    parser.add_argument(
        '--n-before',
        type=int,
        help='Number of records before center timestamp'
    )
    parser.add_argument(
        '--n-after',
        type=int,
        help='Number of records after center timestamp'
    )
    
    return parser.parse_args()


def validate_args(args) -> str:
    """Validate command-line arguments and determine query mode.
    
    Args:
        args: Parsed arguments namespace
    
    Returns:
        Query mode: 'ALL', 'RANGE', or 'NEIGHBORHOOD'
    
    Raises:
        ValidationError: If arguments are invalid or ambiguous
    """
    # Validate symbol format
    if not validate_symbol_format(args.symbol):
        raise ValidationError(
            f"Invalid symbol format: {args.symbol}. "
            f"Symbol must be alphanumeric and uppercase (e.g., BTCUSDT)",
            context={"symbol": args.symbol}
        )
    
    # Validate timeframe
    if not validate_timeframe(args.timeframe):
        raise ValidationError(
            f"Invalid timeframe: {args.timeframe}",
            context={"timeframe": args.timeframe}
        )
    
    # Determine query mode
    mode_count = sum([
        args.all,
        bool(args.from_timestamp or args.to_timestamp),
        bool(args.center_timestamp or args.n_before is not None or args.n_after is not None),
    ])
    
    if mode_count == 0:
        raise ValidationError(
            "No query mode specified. Use one of: --all, --from/--to, or --timestamp/--n-before/--n-after"
        )
    
    if mode_count > 1:
        raise ValidationError(
            "Multiple query modes specified. Use only one: --all, --from/--to, or --timestamp/--n-before/--n-after"
        )
    
    # Validate mode-specific arguments
    if args.all:
        return 'ALL'
    
    if args.from_timestamp or args.to_timestamp:
        if not (args.from_timestamp and args.to_timestamp):
            raise ValidationError(
                "RANGE mode requires both --from and --to timestamps"
            )
        return 'RANGE'
    
    if args.center_timestamp or args.n_before is not None or args.n_after is not None:
        if not (args.center_timestamp and args.n_before is not None and args.n_after is not None):
            raise ValidationError(
                "NEIGHBORHOOD mode requires --timestamp, --n-before, and --n-after"
            )
        if args.n_before < 0 or args.n_after < 0:
            raise ValidationError(
                "Record counts (--n-before, --n-after) must be non-negative"
            )
        return 'NEIGHBORHOOD'
    
    # Should never reach here
    raise ValidationError("Unable to determine query mode")


def main():
    """Main entry point."""
    # Parse arguments
    args = parse_args()
    
    # Initialize logger (before config to catch config errors)
    logger = build_logger(
        service_name="bq-stock-extractor",
        environment="development",
        level="INFO",
    )
    
    # Generate unique request ID for this extraction
    request_id = set_request_id()
    
    try:
        # Validate arguments and determine query mode
        query_mode = validate_args(args)
        
        log_struct(
            logger,
            "INFO",
            f"Starting BigQuery extraction in {query_mode} mode",
            labels={
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "mode": query_mode,
            },
            fields={
                "exchange": args.exchange,
                "output_dir": args.output,
                "request_id": request_id,
            }
        )
        
        # Load configuration
        config = load_config()
        
        # Initialize components
        query_builder = QueryBuilder(config.bq_table_fqn)
        bq_client = BigQueryClient(config, logger)
        output_handler = OutputHandler(logger)
        
        # Build query based on mode
        if query_mode == 'ALL':
            sql = query_builder.build_all_query(
                args.symbol,
                args.timeframe,
                args.exchange,
            )
        elif query_mode == 'RANGE':
            from_ts = parse_timestamp(args.from_timestamp)
            to_ts = parse_timestamp(args.to_timestamp)
            sql = query_builder.build_range_query(
                args.symbol,
                args.timeframe,
                from_ts,
                to_ts,
                args.exchange,
            )
        else:  # NEIGHBORHOOD
            center_ts = parse_timestamp(args.center_timestamp)
            sql = query_builder.build_neighborhood_query(
                args.symbol,
                args.timeframe,
                center_ts,
                args.n_before,
                args.n_after,
                args.exchange,
            )
        
        # Execute query
        rows = bq_client.execute_query(
            sql,
            context={
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "mode": query_mode,
            }
        )
        
        # Check if any data returned
        if not rows:
            log_struct(
                logger,
                "WARNING",
                "No data found for query",
                labels={
                    "symbol": args.symbol,
                    "timeframe": args.timeframe,
                },
                fields={}
            )
            raise DataNotFoundError(
                f"No data found for symbol={args.symbol}, timeframe={args.timeframe}",
                context={
                    "symbol": args.symbol,
                    "timeframe": args.timeframe,
                    "mode": query_mode,
                }
            )
        
        # Transform results
        transformed_data = output_handler.transform_results(rows)
        
        # Build metadata
        metadata = {
            "request_id": get_request_id() or "N/A",
            "request_timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "symbol": args.symbol,
            "timeframe": args.timeframe,
            "query_type": query_mode.lower(),
            "query_parameters": {}
        }
        
        # Add query-specific parameters
        if query_mode == 'RANGE':
            metadata["query_parameters"] = {
                "from_timestamp": args.from_timestamp,
                "to_timestamp": args.to_timestamp,
            }
        elif query_mode == 'NEIGHBORHOOD':
            metadata["query_parameters"] = {
                "center_timestamp": args.center_timestamp,
                "n_before": args.n_before,
                "n_after": args.n_after,
            }
        # ALL mode has no parameters (empty dict already set)
        
        # Save to file with metadata
        output_path = Path(args.output)
        file_path = output_handler.save_to_file(
            transformed_data,
            output_path,
            args.symbol,
            args.timeframe,
            metadata=metadata,
        )
        
        # Success
        log_struct(
            logger,
            "INFO",
            f"Extraction completed successfully: {file_path}",
            labels={
                "symbol": args.symbol,
                "timeframe": args.timeframe,
            },
            fields={
                "file_path": str(file_path),
                "record_count": len(transformed_data),
            }
        )
        
        print(f"Success! Data saved to: {file_path}")
        print(f"Records: {len(transformed_data)}")
        
        # Close client
        bq_client.close()
        
        return 0
        
    except BQExtractorError as exc:
        # Handle our custom exceptions
        log_struct(
            logger,
            "ERROR",
            f"Extraction failed: {exc.message}",
            labels={
                "error_type": exc.__class__.__name__,
            },
            fields=exc.to_dict(),
        )
        
        print(f"Error: {exc.message}", file=sys.stderr)
        
        if exc.context:
            print(f"Context: {exc.context}", file=sys.stderr)
        
        return exc.exit_code
        
    except Exception as exc:
        # Handle unexpected exceptions
        log_struct(
            logger,
            "ERROR",
            f"Unexpected error: {str(exc)}",
            labels={},
            fields={"exception_type": type(exc).__name__}
        )
        
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

