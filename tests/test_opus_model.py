import unittest
from app.agents.metrics_agent import metrics_agent
from app.agents.deploy_agent import deploy_agent

class TestOpusModelConfiguration(unittest.TestCase):
    
    def test_metrics_agent_model(self):
        print(f"\nChecking metrics_agent model: {metrics_agent.model}")
        self.assertEqual(metrics_agent.name, "metrics_agent")
        self.assertEqual(metrics_agent.model, "bedrock/us.anthropic.claude-opus-4-5-20251101-v1:0")

    def test_deploy_agent_model(self):
        print(f"Checking deploy_agent model: {deploy_agent.model}")
        self.assertEqual(deploy_agent.name, "deploy_agent")
        self.assertEqual(deploy_agent.model, "bedrock/us.anthropic.claude-opus-4-5-20251101-v1:0")

if __name__ == "__main__":
    unittest.main()
