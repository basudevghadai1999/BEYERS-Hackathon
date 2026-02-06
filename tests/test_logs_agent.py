import unittest
from unittest.mock import patch, MagicMock
from app.agents.logs_agent import analyze_logs
import datetime

class TestLogsAgent(unittest.TestCase):
    
    @patch("app.tools.cloudwatch_logs.boto3.client")
    def test_analyze_logs(self, mock_boto):
        # Mocking CloudWatch response
        mock_cw = MagicMock()
        mock_boto.return_value = mock_cw
        
        # Mocking the response from get_query_results
        mock_cw.get_query_results.return_value = {
            "status": "Complete",
            "results": [
                [
                    {"field": "@timestamp", "value": "2026-02-06 14:30:00.000"},
                    {"field": "@message", "value": "Connection timeout"},
                    {"field": "level", "value": "ERROR"},
                    {"field": "error_code", "value": "DB_CONN_TIMEOUT"},
                    {"field": "stack_trace", "value": "com.bayer.checkout.db.ConnectionPool.acquire(ConnectionPool.java:142)"}
                ]
            ]
        }
        mock_cw.start_query.return_value = {"queryId": "test-query-id"}
        
        service = "checkout-service"
        time_window = {
            "start": "2026-02-06T14:00:00Z",
            "end": "2026-02-06T14:35:00Z",
            "incident_id": "INC-20260206-TEST-LOGS"
        }
        
        result = analyze_logs(service, time_window)
        
        self.assertEqual(result["agent"], "logs_agent")
        self.assertEqual(result["incident_id"], "INC-20260206-TEST-LOGS")
        self.assertTrue(len(result["findings"]) > 0)
        
        findings = result["findings"][0]
        self.assertEqual(findings["matched_entries"], 1)
        self.assertIn("DB_CONN_TIMEOUT", findings["error_summary"])
        
        sample = findings["sample_entries"][0]
        self.assertEqual(sample["error_code"], "DB_CONN_TIMEOUT")
        self.assertIn("parsed_stack_trace", sample)
        self.assertEqual(sample["parsed_stack_trace"]["root_frame"]["class"], "ConnectionPool")
        
        # Verify Smart Summary
        self.assertIn("summary", result)
        self.assertIn("Detected 1 error logs", result["summary"])

if __name__ == "__main__":
    unittest.main()
