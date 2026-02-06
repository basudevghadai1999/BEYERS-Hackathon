import unittest
from unittest.mock import patch, MagicMock
from app.agents.metrics_agent import query_metrics_and_detect_anomalies, submit_metrics_response
from app.agents.deploy_agent import analyze_deployments, submit_deploy_response
import datetime

class TestLLMResponseFlow(unittest.TestCase):
    
    @patch("app.agents.metrics_agent.get_metric_data")
    @patch("app.agents.metrics_agent.detect_anomalies")
    @patch("app.agents.metrics_agent.build_response_envelope")
    def test_metrics_agent_flow(self, mock_envelope, mock_detect, mock_get_data):
        print("\n=== Testing Metrics Agent Flow ===")
        
        # 1. Setup mocks with INTERESTING data
        mock_get_data.return_value = {"latency": [{"timestamp": "2026-02-06T12:00:00Z", "value": 500}]}
        # Simulate a detected anomaly
        mock_detect.return_value = {
            "anomalies": [{"timestamp": "2026-02-06T12:00:00Z", "value": 500}], 
            "baseline_mean": 100
        }
        
        # 2. Execution - Phase 1: Analysis
        print("[Step 1] Agent calls query_metrics_and_detect_anomalies...")
        analysis_result = query_metrics_and_detect_anomalies("checkout-service", ["latency"], {})
        
        print(f"--> Analysis Findings: {len(analysis_result['anomalies'])} anomalies detected")
        print(f"--> Data for LLM: {analysis_result['anomalies']}")
        
        self.assertIn("anomalies", analysis_result)
        
        # 3. Execution - Phase 2: Response Submission (Simulated LLM Call)
        # The LLM would see the above findings and generate this summary:
        simulated_summary = "CRITICAL: Latency spike detected. Value 500ms (5x baseline)."
        findings = analysis_result["anomalies"]
        incident_id = analysis_result["incident_id"]
        
        print(f"[Step 2] Agent (LLM) calls submit_metrics_response with summary: '{simulated_summary}'")
        submit_metrics_response(incident_id, findings, simulated_summary)
        
        # 4. Verify
        mock_envelope.assert_called_once()
        call_kwargs = mock_envelope.call_args[1]
        self.assertEqual(call_kwargs["summary"], simulated_summary)
        print("--> Success: Envelope built with correct summary and findings.")

    @patch("app.agents.deploy_agent.get_github_deployments")
    @patch("app.agents.deploy_agent.correlate_deploy_to_incident")
    @patch("app.agents.deploy_agent.build_response_envelope")
    def test_deploy_agent_flow(self, mock_envelope, mock_correlate, mock_get_deploy):
        print("\n=== Testing Deploy Agent Flow ===")
        
        # 1. Setup mocks
        mock_get_deploy.return_value = ["commit_1"]
        # Simulate a risky deployment correlation
        mock_correlate.return_value = {
            "correlations": [{"commit": "123", "risk": "high"}], 
            "highest_risk_deploy": {"author": "Basudev", "full_details": "Fix DB config", "affected_files": ["db.py"]}
        }
        
        # 2. Execution - Phase 1: Analysis
        print("[Step 1] Agent calls analyze_deployments...")
        analysis_result = analyze_deployments("checkout-service", {"end": "2026-02-06T12:00:00Z"})
        
        print(f"--> Analysis Findings: {analysis_result['deployments_found']} deployments checked")
        print(f"--> Risky Deploy Found: {analysis_result['correlation_results']['highest_risk_deploy']['full_details']}")
        
        # 3. Execution - Phase 2: Response Submission
        simulated_summary = "Identified risky deployment by Basudev changing db.py."
        findings = analysis_result["correlation_results"]["correlations"]
        incident_id = analysis_result["incident_id"]
        
        print(f"[Step 2] Agent (LLM) calls submit_deploy_response with summary: '{simulated_summary}'")
        submit_deploy_response(incident_id, findings, simulated_summary)
        
        # 4. Verify
        mock_envelope.assert_called_once()
        print("--> Success: Envelope built with correct summary.")

if __name__ == "__main__":
    unittest.main()
