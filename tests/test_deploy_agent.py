import unittest
from unittest.mock import patch, MagicMock
from app.agents.deploy_agent import analyze_deployments
import datetime

class TestDeployAgent(unittest.TestCase):
    
    @patch("app.tools.github_deployments.subprocess.run")
    def test_analyze_deployments(self, mock_run):
        # 1. Mock git log (hashes and dates)
        mock_log = MagicMock()
        mock_log.stdout = "hash123|2026-02-06T14:40:00+00:00\nhash456|2026-02-06T12:00:00+00:00"
        
        # 2. Mock git show for each hash
        mock_show_1 = MagicMock()
        mock_show_1.stdout = "hash123|Basudev|2026-02-06T14:40:00+00:00|Config change: Reduce DB pool size|This change limits the pool size to 50.\n\napp/config/db.py"
        
        mock_show_2 = MagicMock()
        mock_show_2.stdout = "hash456|Lokesh|2026-02-06T12:00:00+00:00|Add mock data|Adding S3 mock files.\n\nmock_data/logs/file.json"
        
        # side_effect to return mocks in order
        mock_run.side_effect = [mock_log, mock_show_1, mock_show_2]
        
        service = "checkout-service"
        time_window = {
            "start": "2026-02-06T11:00:00Z",
            "end": "2026-02-06T15:00:00Z",
            "incident_id": "INC-DEPLOY-TEST"
        }
        
        # Anomaly started at 14:45
        result = analyze_deployments(service, time_window, anomaly_start="2026-02-06T14:45:00Z")
        
        self.assertEqual(result["agent"], "deploy_agent")
        self.assertEqual(len(result["findings"]), 2)
        
        # Verify detailed summary
        self.assertIn("summary", result)
        self.assertIn("by **Basudev**", result["summary"])
        self.assertIn("Service: **checkout-service**", result["summary"])
        self.assertIn("app/config/db.py", result["summary"])
        self.assertIn("🚨", result["summary"])

    @patch("app.tools.github_deployments.subprocess.run")
    def test_deploy_error_handling(self, mock_run):
        mock_run.side_effect = Exception("Git command failed")
        
        service = "checkout-service"
        time_window = {"start": "2026-02-06T11:00:00Z", "end": "2026-02-06T15:00:00Z"}
        
        result = analyze_deployments(service, time_window)
        
        self.assertEqual(result["status"], "failed")
        self.assertIn("Git command failed", result["summary"])

if __name__ == "__main__":
    unittest.main()
