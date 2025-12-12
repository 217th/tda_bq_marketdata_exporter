"""
Unit tests for request ID tracking in logging module.

Tests the contextvars-based request ID propagation system.
"""

import json
import logging
import unittest
from io import StringIO

from src.logger import (
    build_logger,
    set_request_id,
    get_request_id,
    clear_request_id,
    log_struct,
    StructuredFormatter,
)


class TestRequestIDContext(unittest.TestCase):
    """Test request ID context variable management."""
    
    def setUp(self):
        """Clear request ID before each test."""
        clear_request_id()
    
    def tearDown(self):
        """Clear request ID after each test."""
        clear_request_id()
    
    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        test_id = "test-request-123"
        set_request_id(test_id)
        
        retrieved_id = get_request_id()
        self.assertEqual(retrieved_id, test_id)
    
    def test_set_request_id_auto_generates(self):
        """Test that set_request_id generates UUID if not provided."""
        generated_id = set_request_id()
        
        # Should be a valid UUID string
        self.assertIsNotNone(generated_id)
        self.assertIsInstance(generated_id, str)
        self.assertEqual(len(generated_id), 36)  # UUID4 format: 8-4-4-4-12
        self.assertIn('-', generated_id)
    
    def test_get_request_id_returns_none_when_not_set(self):
        """Test that get_request_id returns None when not set."""
        result = get_request_id()
        self.assertIsNone(result)
    
    def test_clear_request_id(self):
        """Test clearing request ID."""
        set_request_id("test-123")
        self.assertIsNotNone(get_request_id())
        
        clear_request_id()
        self.assertIsNone(get_request_id())
    
    def test_request_id_isolation(self):
        """Test that request IDs don't interfere with each other."""
        # Set first request ID
        id1 = set_request_id("request-1")
        self.assertEqual(get_request_id(), "request-1")
        
        # Set second request ID (overwrites)
        id2 = set_request_id("request-2")
        self.assertEqual(get_request_id(), "request-2")
        self.assertNotEqual(id1, id2)


class TestStructuredFormatterWithRequestID(unittest.TestCase):
    """Test that StructuredFormatter includes request ID in log output."""
    
    def setUp(self):
        """Set up logger with string stream for testing."""
        clear_request_id()
        
        # Create logger with StringIO handler
        self.logger = logging.getLogger("test-logger")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = []
        
        self.stream = StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def tearDown(self):
        """Clean up."""
        clear_request_id()
        self.logger.handlers = []
    
    def test_log_includes_request_id_when_set(self):
        """Test that log messages include request_id when it's set."""
        test_request_id = "test-abc-123"
        set_request_id(test_request_id)
        
        self.logger.info("Test message")
        
        # Parse JSON log output
        log_output = self.stream.getvalue().strip()
        log_data = json.loads(log_output)
        
        # Verify request_id is present
        self.assertIn("request_id", log_data)
        self.assertEqual(log_data["request_id"], test_request_id)
    
    def test_log_works_without_request_id(self):
        """Test that logging works normally when request_id is not set."""
        # Don't set request ID
        self.logger.info("Test message without request ID")
        
        # Parse JSON log output
        log_output = self.stream.getvalue().strip()
        log_data = json.loads(log_output)
        
        # Verify request_id is NOT present
        self.assertNotIn("request_id", log_data)
        
        # Verify other fields are present
        self.assertIn("timestamp", log_data)
        self.assertIn("level", log_data)
        self.assertIn("message", log_data)
    
    def test_log_struct_with_request_id(self):
        """Test log_struct function with request ID in context."""
        test_request_id = "req-xyz-789"
        set_request_id(test_request_id)
        
        log_struct(
            self.logger,
            "INFO",
            "Structured log message",
            labels={"symbol": "BTCUSDT"},
            fields={"operation": "query"}
        )
        
        # Parse JSON log output
        log_output = self.stream.getvalue().strip()
        log_data = json.loads(log_output)
        
        # Verify request_id is present
        self.assertEqual(log_data["request_id"], test_request_id)
        
        # Verify other structured data is present
        self.assertIn("labels", log_data)
        self.assertEqual(log_data["labels"]["symbol"], "BTCUSDT")
        self.assertIn("fields", log_data)
        self.assertEqual(log_data["fields"]["operation"], "query")
    
    def test_multiple_log_messages_same_request_id(self):
        """Test that multiple log messages share the same request ID."""
        request_id = set_request_id()
        
        # Log multiple messages
        self.logger.info("Message 1")
        self.logger.warning("Message 2")
        self.logger.error("Message 3")
        
        # Parse all log outputs
        log_outputs = self.stream.getvalue().strip().split('\n')
        self.assertEqual(len(log_outputs), 3)
        
        # Verify all have the same request_id
        for log_line in log_outputs:
            log_data = json.loads(log_line)
            self.assertIn("request_id", log_data)
            self.assertEqual(log_data["request_id"], request_id)
    
    def test_request_id_persists_across_log_levels(self):
        """Test that request ID persists across different log levels."""
        test_request_id = "persist-test-456"
        set_request_id(test_request_id)
        
        # Log at different levels
        self.logger.debug("Debug message")
        self.logger.info("Info message")
        self.logger.warning("Warning message")
        self.logger.error("Error message")
        
        log_outputs = self.stream.getvalue().strip().split('\n')
        
        # All logs should have the same request_id
        for log_line in log_outputs:
            if log_line:  # Skip empty lines
                log_data = json.loads(log_line)
                self.assertEqual(log_data["request_id"], test_request_id)


class TestRequestIDIntegration(unittest.TestCase):
    """Integration tests for request ID in realistic scenarios."""
    
    def setUp(self):
        """Set up logger."""
        clear_request_id()
        self.stream = StringIO()
        self.logger = build_logger("test-service", "test-env", "INFO")
        
        # Replace handler with one that writes to StringIO
        self.logger.handlers = []
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def tearDown(self):
        """Clean up."""
        clear_request_id()
    
    def test_end_to_end_request_tracking(self):
        """Test end-to-end request tracking scenario."""
        # Simulate start of request
        request_id = set_request_id()
        
        # Simulate logging at different stages
        log_struct(self.logger, "INFO", "Request started", 
                  labels={"stage": "init"}, fields={"request_id": request_id})
        log_struct(self.logger, "INFO", "Query building",
                  labels={"stage": "query"}, fields={})
        log_struct(self.logger, "INFO", "Query execution",
                  labels={"stage": "execute"}, fields={})
        log_struct(self.logger, "INFO", "Request completed",
                  labels={"stage": "complete"}, fields={})
        
        # Parse all logs
        log_outputs = self.stream.getvalue().strip().split('\n')
        self.assertEqual(len(log_outputs), 4)
        
        # Verify all logs have the same request_id
        for log_line in log_outputs:
            log_data = json.loads(log_line)
            self.assertEqual(log_data["request_id"], request_id)
    
    def test_different_requests_different_ids(self):
        """Test that different requests get different IDs."""
        # First request
        request_id_1 = set_request_id()
        self.logger.info("Request 1")
        
        # Second request (new ID)
        request_id_2 = set_request_id()
        self.logger.info("Request 2")
        
        # Verify different IDs
        self.assertNotEqual(request_id_1, request_id_2)
        
        # Parse logs
        log_outputs = self.stream.getvalue().strip().split('\n')
        log_1 = json.loads(log_outputs[0])
        log_2 = json.loads(log_outputs[1])
        
        self.assertEqual(log_1["request_id"], request_id_1)
        self.assertEqual(log_2["request_id"], request_id_2)


if __name__ == "__main__":
    unittest.main()

