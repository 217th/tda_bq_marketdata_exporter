"""
Google Cloud Storage handler for BigQuery Stock Quotes Extractor.

Handles file uploads to GCS bucket and generates public download URLs.
"""

import logging
from pathlib import Path
from typing import Optional

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from google.api_core import exceptions as google_exceptions

from .exceptions import GCSUploadError, GCSAuthenticationError
from .logger import log_struct


class GCSHandler:
    """Handles uploads to Google Cloud Storage bucket.
    
    This class encapsulates all GCS operations including:
    - Client initialization with service account credentials
    - File uploads with proper content types
    - Public download URL generation
    - Comprehensive error handling
    """
    
    def __init__(self, bucket_name: str, credentials_path: Path, logger: logging.Logger):
        """Initialize GCS client with service account credentials.
        
        Args:
            bucket_name: Name of the GCS bucket
            credentials_path: Path to service account JSON key file
            logger: Logger instance for structured logging
        
        Raises:
            GCSAuthenticationError: If credentials are invalid or bucket access fails
        """
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        self.logger = logger
        
        try:
            # Initialize storage client with explicit credentials
            self.client = storage.Client.from_service_account_json(
                str(credentials_path)
            )
            
            # Get bucket reference
            # Note: We don't check bucket.exists() here because it requires
            # storage.buckets.get permission. If the bucket doesn't exist or
            # is inaccessible, we'll get an error on the first upload attempt.
            self.bucket = self.client.bucket(bucket_name)
            
            log_struct(
                self.logger,
                "INFO",
                f"GCS handler initialized successfully for bucket: {bucket_name}",
                labels={"bucket": bucket_name},
                fields={}
            )
            
        except google_exceptions.Forbidden as exc:
            raise GCSAuthenticationError(
                f"Permission denied accessing GCS bucket '{bucket_name}'. "
                f"Check service account permissions.",
                context={
                    "bucket_name": bucket_name,
                    "error": str(exc),
                }
            )
        except google_exceptions.Unauthorized as exc:
            raise GCSAuthenticationError(
                f"Invalid GCS credentials. Check service account key file: {credentials_path}",
                context={
                    "credentials_path": str(credentials_path),
                    "error": str(exc),
                }
            )
        except FileNotFoundError as exc:
            raise GCSAuthenticationError(
                f"GCS service account key file not found: {credentials_path}",
                context={
                    "credentials_path": str(credentials_path),
                }
            )
        except GoogleCloudError as exc:
            raise GCSAuthenticationError(
                f"Failed to initialize GCS client: {exc}",
                context={
                    "bucket_name": bucket_name,
                    "credentials_path": str(credentials_path),
                    "error": str(exc),
                }
            )
    
    def upload_file(self, local_file_path: Path, object_name: str) -> str:
        """Upload local file to GCS bucket.
        
        Args:
            local_file_path: Path to local file to upload
            object_name: Name for object in bucket (e.g., 'request_id.json')
        
        Returns:
            Public download URL for the uploaded file
        
        Raises:
            GCSUploadError: If upload fails
        
        Example:
            >>> handler = GCSHandler('my-bucket', Path('key.json'), logger)
            >>> url = handler.upload_file(Path('data.json'), 'abc123.json')
            >>> print(url)
            https://storage.googleapis.com/my-bucket/abc123.json
        """
        try:
            # Validate local file exists
            if not local_file_path.exists():
                raise GCSUploadError(
                    f"Local file not found: {local_file_path}",
                    context={
                        "local_file_path": str(local_file_path),
                        "object_name": object_name,
                    }
                )
            
            # Get file size for logging
            file_size = local_file_path.stat().st_size
            
            log_struct(
                self.logger,
                "INFO",
                f"Uploading file to GCS: {object_name}",
                labels={
                    "bucket": self.bucket_name,
                    "object_name": object_name,
                },
                fields={
                    "local_file": str(local_file_path),
                    "file_size_bytes": file_size,
                }
            )
            
            # Create blob (object) reference
            blob = self.bucket.blob(object_name)
            
            # Upload file with appropriate content type for JSON
            blob.upload_from_filename(
                str(local_file_path),
                content_type='application/json'
            )
            
            # Generate public download URL
            download_url = self.generate_download_url(object_name)
            
            log_struct(
                self.logger,
                "INFO",
                f"File uploaded successfully to GCS",
                labels={
                    "bucket": self.bucket_name,
                    "object_name": object_name,
                },
                fields={
                    "download_url": download_url,
                    "file_size_bytes": file_size,
                }
            )
            
            return download_url
            
        except google_exceptions.Forbidden as exc:
            raise GCSUploadError(
                f"Permission denied uploading to GCS bucket '{self.bucket_name}'. "
                f"Check 'Storage Object Creator' role.",
                context={
                    "bucket_name": self.bucket_name,
                    "object_name": object_name,
                    "error": str(exc),
                },
                retryable=False  # Permission errors are not retryable
            )
        except google_exceptions.ServiceUnavailable as exc:
            raise GCSUploadError(
                f"GCS service temporarily unavailable: {exc}",
                context={
                    "bucket_name": self.bucket_name,
                    "object_name": object_name,
                    "error": str(exc),
                },
                retryable=True  # Service errors can be retried
            )
        except GoogleCloudError as exc:
            raise GCSUploadError(
                f"Failed to upload file to GCS: {exc}",
                context={
                    "bucket_name": self.bucket_name,
                    "object_name": object_name,
                    "local_file": str(local_file_path),
                    "error": str(exc),
                },
                retryable=True  # Generic GCS errors might be transient
            )
        except Exception as exc:
            # Catch any unexpected errors
            raise GCSUploadError(
                f"Unexpected error uploading to GCS: {exc}",
                context={
                    "bucket_name": self.bucket_name,
                    "object_name": object_name,
                    "local_file": str(local_file_path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    
    def generate_download_url(self, object_name: str) -> str:
        """Generate publicly accessible download URL.
        
        Since the bucket has 'allUsers' with 'Storage Object Viewer' permission,
        we can use the simple public URL format.
        
        Args:
            object_name: Name of the object in the bucket
        
        Returns:
            Public HTTP download URL
        
        Example:
            >>> handler = GCSHandler('my-bucket', Path('key.json'), logger)
            >>> url = handler.generate_download_url('abc123.json')
            >>> print(url)
            https://storage.googleapis.com/my-bucket/abc123.json
        """
        # Standard public GCS URL format
        return f"https://storage.googleapis.com/{self.bucket_name}/{object_name}"

