import unittest
from unittest.mock import patch, MagicMock
from app.agents.metrics_agent import query_metrics_and_detect_anomalies
import datetime

class TestMetricsAgent(unittest.TestCase):
    
    @patch("app.tools.cloudwatch_metrics.boto3.client")
    def test_query_metrics_and_detect_anomalies(self, mock_boto):
        # Mocking CloudWatch response
        mock_cw = MagicMock()
        mock_boto.return_value = mock_cw
        
        # Mocking the response from get_metric_data
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_cw.get_metric_data.return_value = {
            "MetricDataResults": [
                {
                    "Id": "m0",
                    "Timestamps": [now - datetime.timedelta(minutes=i) for i in range(20)],
                    "Values": [100.0] * 15 + [2000.0, 2100.0] + [100.0] * 3
                }
            ]
        }
        
        service = "checkout-service"
        metric_names = ["p99_latency_ms"]
        time_window = {
            "start": (now - datetime.timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "incident_id": "INC-20260206-TEST"
        }
        
        result = query_metrics_and_detect_anomalies(service, metric_names, time_window)
        
        self.assertEqual(result["agent"], "metrics_agent")
        self.assertEqual(result["incident_id"], "INC-20260206-TEST")
        self.assertTrue(len(result["findings"]) > 0)
        
        finding = result["findings"][0]
        self.assertEqual(finding["metric_name"], "p99_latency_ms")
        self.assertGreater(finding["change_factor"], 10) # 2100 vs ~100
        
        # Verify Smart Summary
        self.assertIn("summary", result)
        self.assertIn("threshold 2000ms exceeded", result["summary"])

    @patch("app.tools.cloudwatch_metrics.boto3.client")
    def test_query_metrics_error_handling(self, mock_boto):
        # Mocking an exception from CloudWatch
        mock_cw = MagicMock()
        mock_boto.return_value = mock_cw
        mock_cw.get_metric_data.side_effect = Exception("CloudWatch API Error")
        
        service = "checkout-service"
        metric_names = ["p99_latency_ms"]
        time_window = {
            "start": "2026-02-06T14:40:00Z",
            "end": "2026-02-06T14:45:00Z"
        }
        
        result = query_metrics_and_detect_anomalies(service, metric_names, time_window)
        
        # Verify the agent returns a standard failed response with detail
        self.assertEqual(result["agent"], "metrics_agent")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)
        self.assertIn("Agent execution failed", result["summary"])

if __name__ == "__main__":
    unittest.main()
