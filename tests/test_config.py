"""
Unit tests for configuration module.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.config import Config, load_config, BACKOFF_BASE, BACKOFF_FACTOR, BACKOFF_MAX, BACKOFF_ATTEMPTS


class TestConfig:
    """Test Config dataclass."""
    
    def test_bq_table_fqn(self):
        """Test fully qualified table name property."""
        config = Config(
            gcp_project_id="test-project",
            bq_dataset="test_dataset",
            bq_table="test_table",
            gcp_key_path=Path("/tmp/test-key.json"),
            service_name="test-service",
            environment="test",
            log_level="INFO",
        )
        
        assert config.bq_table_fqn == "test-project.test_dataset.test_table"
    
    def test_validate_missing_key_file(self, tmp_path):
        """Test validation fails when GCP key file doesn't exist."""
        config = Config(
            gcp_project_id="test-project",
            bq_dataset="test_dataset",
            bq_table="test_table",
            gcp_key_path=tmp_path / "nonexistent.json",
            service_name="test-service",
            environment="test",
            log_level="INFO",
        )
        
        with pytest.raises(ValueError, match="GCP key file not found"):
            config.validate()
    
    def test_validate_invalid_log_level(self, tmp_path):
        """Test validation fails with invalid log level."""
        key_file = tmp_path / "test-key.json"
        key_file.write_text("{}")
        
        config = Config(
            gcp_project_id="test-project",
            bq_dataset="test_dataset",
            bq_table="test_table",
            gcp_key_path=key_file,
            service_name="test-service",
            environment="test",
            log_level="INVALID",
        )
        
        with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
            config.validate()
    
    def test_validate_empty_required_fields(self, tmp_path):
        """Test validation fails with empty required fields."""
        key_file = tmp_path / "test-key.json"
        key_file.write_text("{}")
        
        config = Config(
            gcp_project_id="",
            bq_dataset="test_dataset",
            bq_table="test_table",
            gcp_key_path=key_file,
            service_name="test-service",
            environment="test",
            log_level="INFO",
        )
        
        with pytest.raises(ValueError, match="GCP_PROJECT_ID cannot be empty"):
            config.validate()
    
    def test_validate_success(self, tmp_path):
        """Test validation succeeds with valid config."""
        key_file = tmp_path / "test-key.json"
        key_file.write_text("{}")
        
        config = Config(
            gcp_project_id="test-project",
            bq_dataset="test_dataset",
            bq_table="test_table",
            gcp_key_path=key_file,
            service_name="test-service",
            environment="test",
            log_level="INFO",
        )
        
        # Should not raise
        config.validate()


class TestLoadConfig:
    """Test load_config function."""
    
    def test_load_config_missing_env_file(self):
        """Test load_config fails when .env file doesn't exist."""
        with pytest.raises(FileNotFoundError, match=".env file not found"):
            load_config(Path("/tmp/nonexistent.env"))
    
    def test_load_config_missing_required_vars(self, tmp_path):
        """Test load_config fails with missing required variables."""
        env_file = tmp_path / ".env"
        env_file.write_text("GCP_PROJECT_ID=test-project\n")
        
        with pytest.raises(ValueError, match="Missing required environment variables"):
            load_config(env_file)
    
    def test_load_config_success(self, tmp_path):
        """Test load_config succeeds with valid .env file."""
        # Create .env file
        env_file = tmp_path / ".env"
        key_file = tmp_path / "test-key.json"
        key_file.write_text("{}")
        
        env_content = f"""
GCP_PROJECT_ID=test-project
BQ_DATASET=test_dataset
BQ_TABLE=test_table
GCP_KEY_PATH={key_file}
SERVICE_NAME=test-service
ENVIRONMENT=test
LOG_LEVEL=DEBUG
"""
        env_file.write_text(env_content)
        
        config = load_config(env_file)
        
        assert config.gcp_project_id == "test-project"
        assert config.bq_dataset == "test_dataset"
        assert config.bq_table == "test_table"
        assert config.gcp_key_path == key_file
        assert config.service_name == "test-service"
        assert config.environment == "test"
        assert config.log_level == "DEBUG"
    
    def test_load_config_with_defaults(self, tmp_path, monkeypatch):
        """Test load_config uses defaults for optional variables."""
        # Clear optional environment variables
        monkeypatch.delenv("SERVICE_NAME", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        
        env_file = tmp_path / ".env"
        key_file = tmp_path / "test-key.json"
        key_file.write_text("{}")
        
        env_content = f"""
GCP_PROJECT_ID=test-project
BQ_DATASET=test_dataset
BQ_TABLE=test_table
GCP_KEY_PATH={key_file}
"""
        env_file.write_text(env_content)
        
        config = load_config(env_file)
        
        assert config.service_name == "bq-stock-extractor"
        assert config.environment == "development"
        assert config.log_level == "INFO"


class TestBackoffConstants:
    """Test backoff configuration constants."""
    
    def test_backoff_constants(self):
        """Test backoff constants have expected values."""
        assert BACKOFF_BASE == 1.0
        assert BACKOFF_FACTOR == 2.0
        assert BACKOFF_MAX == 32.0
        assert BACKOFF_ATTEMPTS == 5

