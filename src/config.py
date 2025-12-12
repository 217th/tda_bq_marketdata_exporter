"""
Configuration module for BigQuery Stock Quotes Extractor.

Loads and validates environment variables from .env file.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # Google Cloud / BigQuery
    gcp_project_id: str
    bq_dataset: str
    bq_table: str
    gcp_key_path: Path
    
    # Application
    service_name: str
    environment: str
    log_level: str
    
    @property
    def bq_table_fqn(self) -> str:
        """Fully qualified BigQuery table name."""
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_table}"
    
    def validate(self) -> None:
        """Validate configuration values.
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate GCP key file exists
        if not self.gcp_key_path.exists():
            raise ValueError(
                f"GCP key file not found: {self.gcp_key_path}. "
                f"Please check GCP_KEY_PATH in .env file."
            )
        
        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid LOG_LEVEL: {self.log_level}. "
                f"Must be one of: {', '.join(valid_log_levels)}"
            )
        
        # Validate required string fields are not empty
        required_fields = {
            "GCP_PROJECT_ID": self.gcp_project_id,
            "BQ_DATASET": self.bq_dataset,
            "BQ_TABLE": self.bq_table,
            "SERVICE_NAME": self.service_name,
            "ENVIRONMENT": self.environment,
        }
        
        for field_name, value in required_fields.items():
            if not value or not value.strip():
                raise ValueError(f"{field_name} cannot be empty")


def load_config(env_file: Optional[Path] = None) -> Config:
    """Load configuration from environment variables.
    
    Args:
        env_file: Path to .env file. If None, searches for .env in current directory.
    
    Returns:
        Config: Loaded and validated configuration
    
    Raises:
        FileNotFoundError: If .env file not found
        ValueError: If required variables are missing or invalid
    """
    # Determine .env file path
    if env_file is None:
        env_file = Path.cwd() / ".env"
    else:
        env_file = Path(env_file)
    
    # Load .env file
    if not env_file.exists():
        raise FileNotFoundError(
            f".env file not found: {env_file}\n"
            f"Please create .env file from env.example template."
        )
    
    load_dotenv(env_file)
    
    # Load required variables
    required_vars = [
        "GCP_PROJECT_ID",
        "BQ_DATASET",
        "BQ_TABLE",
        "GCP_KEY_PATH",
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            f"Please check your .env file."
        )
    
    # Create config with defaults for optional variables
    config = Config(
        gcp_project_id=os.getenv("GCP_PROJECT_ID", ""),
        bq_dataset=os.getenv("BQ_DATASET", ""),
        bq_table=os.getenv("BQ_TABLE", ""),
        gcp_key_path=Path(os.getenv("GCP_KEY_PATH", "")),
        service_name=os.getenv("SERVICE_NAME", "bq-stock-extractor"),
        environment=os.getenv("ENVIRONMENT", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    
    # Validate configuration
    config.validate()
    
    return config


# Backoff configuration constants
BACKOFF_BASE = 1.0
BACKOFF_FACTOR = 2.0
BACKOFF_MAX = 32.0
BACKOFF_ATTEMPTS = 5

