"""
BigQuery client wrapper with exponential backoff retry logic.

Implements connection management and query execution with automatic retries
for transient errors.
"""

import logging
from typing import List, Dict, Any, Optional

from google.cloud import bigquery
from google.oauth2 import service_account
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

from .config import Config, BACKOFF_BASE, BACKOFF_FACTOR, BACKOFF_MAX, BACKOFF_ATTEMPTS
from .exceptions import AuthenticationError, QueryExecutionError
from .error_mapper import ErrorMapper


class BigQueryClient:
    """BigQuery client with exponential backoff retry logic."""
    
    def __init__(self, config: Config, logger: logging.Logger):
        """Initialize BigQuery client.
        
        Args:
            config: Application configuration
            logger: Logger instance for structured logging
        
        Raises:
            AuthenticationError: If credentials cannot be loaded
        """
        self.config = config
        self.logger = logger
        self.client: Optional[bigquery.Client] = None
        
        # Initialize client
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize BigQuery client with service account credentials.
        
        Raises:
            AuthenticationError: If credentials are invalid
        """
        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                str(self.config.gcp_key_path),
                scopes=["https://www.googleapis.com/auth/bigquery"],
            )
            
            # Create BigQuery client
            self.client = bigquery.Client(
                project=self.config.gcp_project_id,
                credentials=credentials,
            )
            
            self.logger.info(
                "BigQuery client initialized",
                extra={
                    "labels": {"project": self.config.gcp_project_id},
                    "fields": {},
                }
            )
            
        except Exception as exc:
            # Map to custom exception
            custom_exc = ErrorMapper.map_exception(
                exc,
                context={
                    "project_id": self.config.gcp_project_id,
                    "key_path": str(self.config.gcp_key_path),
                }
            )
            
            self.logger.error(
                f"Failed to initialize BigQuery client: {custom_exc.message}",
                extra={
                    "labels": {},
                    "fields": custom_exc.to_dict(),
                }
            )
            
            raise custom_exc
    
    def _should_retry(self, exception: Exception) -> bool:
        """Determine if exception should trigger retry.
        
        Args:
            exception: Exception that occurred
        
        Returns:
            True if should retry, False otherwise
        """
        return ErrorMapper.is_retryable(exception)
    
    @retry(
        stop=stop_after_attempt(BACKOFF_ATTEMPTS),
        wait=wait_exponential(
            multiplier=BACKOFF_BASE,
            max=BACKOFF_MAX,
            exp_base=BACKOFF_FACTOR,
        ),
        retry=retry_if_exception(lambda exc: ErrorMapper.is_retryable(exc)),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    def execute_query(self, sql: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute BigQuery SQL query with retry logic.
        
        Args:
            sql: SQL query to execute
            context: Additional context for logging (e.g., symbol, timeframe)
        
        Returns:
            List of result rows as dictionaries
        
        Raises:
            QueryExecutionError: If query fails after all retries
            NetworkError: If network error occurs after all retries
        
        Example:
            >>> client = BigQueryClient(config, logger)
            >>> results = client.execute_query(
            ...     "SELECT * FROM table WHERE timestamp >= '2024-01-01'",
            ...     context={"symbol": "BTCUSDT", "mode": "ALL"}
            ... )
        """
        context = context or {}
        
        if not self.client:
            raise QueryExecutionError(
                "BigQuery client not initialized",
                context=context,
            )
        
        try:
            self.logger.info(
                "Executing BigQuery query",
                extra={
                    "labels": context,
                    "fields": {"query_length": len(sql)},
                }
            )
            
            # Execute query
            query_job = self.client.query(sql)
            
            # Wait for query to complete and fetch results
            results = list(query_job.result())
            
            # Convert to list of dictionaries
            rows = [dict(row) for row in results]
            
            self.logger.info(
                f"Query completed successfully, {len(rows)} rows returned",
                extra={
                    "labels": context,
                    "fields": {
                        "row_count": len(rows),
                        "bytes_processed": query_job.total_bytes_processed,
                        "bytes_billed": query_job.total_bytes_billed,
                    },
                }
            )
            
            return rows
            
        except Exception as exc:
            # Map to custom exception
            custom_exc = ErrorMapper.map_exception(
                exc,
                context={
                    **context,
                    "query": sql[:500],  # Include first 500 chars of query
                }
            )
            
            self.logger.error(
                f"Query execution failed: {custom_exc.message}",
                extra={
                    "labels": context,
                    "fields": custom_exc.to_dict(),
                }
            )
            
            # Re-raise the custom exception
            # If retryable, tenacity will catch and retry
            # If not retryable, it will propagate up
            raise custom_exc
    
    def close(self) -> None:
        """Close BigQuery client connection."""
        if self.client:
            self.client.close()
            self.logger.info("BigQuery client closed")

