"""
Unit tests for output handler.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.output_handler import OutputHandler
from src.exceptions import FileSystemError


class TestOutputHandler:
    """Test output handler."""
    
    @pytest.fixture
    def handler(self, mocker):
        """Create output handler instance with mocked logger."""
        mock_logger = mocker.MagicMock()
        return OutputHandler(mock_logger)
    
    @pytest.fixture
    def sample_rows(self):
        """Create sample BigQuery result rows."""
        return [
            {
                "timestamp": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "open": 42000.5,
                "high": 42500.0,
                "low": 41800.0,
                "close": 42300.0,
                "volume": 1234.56,
            },
            {
                "timestamp": datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "open": 42300.0,
                "high": 43000.0,
                "low": 42100.0,
                "close": 42800.0,
                "volume": 2345.67,
            },
        ]
    
    def test_transform_results(self, handler, sample_rows):
        """Test transformation of BigQuery results."""
        transformed = handler.transform_results(sample_rows)
        
        assert len(transformed) == 2
        
        # Check first record
        assert transformed[0]["date"] == "2024-01-01T00:00:00Z"
        assert transformed[0]["open"] == 42000.5
        assert transformed[0]["high"] == 42500.0
        assert transformed[0]["low"] == 41800.0
        assert transformed[0]["close"] == 42300.0
        assert transformed[0]["volume"] == 1234.56
        
        # Check second record
        assert transformed[1]["date"] == "2024-01-02T00:00:00Z"
        assert transformed[1]["open"] == 42300.0
    
    def test_transform_results_only_candle_fields(self, handler):
        """Test that only candle fields are included in output."""
        rows = [
            {
                "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000.0,
                "extra_field": "should_not_appear",
                "another_field": 12345,
            }
        ]
        
        transformed = handler.transform_results(rows)
        
        # Should only have candle fields
        assert set(transformed[0].keys()) == {"date", "open", "high", "low", "close", "volume"}
        assert "extra_field" not in transformed[0]
        assert "another_field" not in transformed[0]
    
    def test_generate_filename(self, handler):
        """Test filename generation."""
        filename = handler.generate_filename(
            "BTCUSDT",
            "1d",
            datetime(2024, 6, 15, 12, 30, 45)
        )
        
        assert filename == "BTCUSDT_1d_20240615_123045.json"
    
    def test_save_to_file(self, handler, sample_rows, tmp_path):
        """Test saving data to file."""
        transformed = handler.transform_results(sample_rows)
        
        file_path = handler.save_to_file(
            transformed,
            tmp_path,
            "BTCUSDT",
            "1d"
        )
        
        # Check file exists
        assert file_path.exists()
        assert file_path.suffix == ".json"
        
        # Check file content
        with open(file_path, 'r') as f:
            loaded_data = json.load(f)
        
        assert len(loaded_data) == 2
        assert loaded_data[0]["date"] == "2024-01-01T00:00:00Z"
        assert loaded_data[0]["open"] == 42000.5
    
    def test_save_to_file_creates_directory(self, handler, tmp_path):
        """Test that save_to_file creates output directory if needed."""
        output_dir = tmp_path / "subdir" / "nested"
        
        data = [
            {
                "date": "2024-01-01T00:00:00Z",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000.0,
            }
        ]
        
        file_path = handler.save_to_file(data, output_dir, "BTCUSDT", "1d")
        
        # Directory should be created
        assert output_dir.exists()
        assert file_path.exists()
    
    def test_save_to_file_empty_data(self, handler, tmp_path):
        """Test saving empty data (no records)."""
        data = []
        
        file_path = handler.save_to_file(data, tmp_path, "BTCUSDT", "1d")
        
        # File should be created with empty array
        assert file_path.exists()
        
        with open(file_path, 'r') as f:
            loaded_data = json.load(f)
        
        assert loaded_data == []
    
    def test_save_to_file_permission_error(self, handler, mocker):
        """Test FileSystemError on permission denied."""
        data = [
            {
                "date": "2024-01-01T00:00:00Z",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000.0,
            }
        ]
        
        # Mock open() to raise PermissionError
        mocker.patch("builtins.open", side_effect=PermissionError("Access denied"))
        
        with pytest.raises(FileSystemError, match="Permission denied"):
            handler.save_to_file(data, Path("/tmp"), "BTCUSDT", "1d")

