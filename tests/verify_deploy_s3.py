import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.deploy_agent import fetch_deployment_logs, deploy_agent

def test_s3_fetch():
    print("Testing fetch_deployment_logs()...")
    result = fetch_deployment_logs()
    
    if "error" in result:
        print(f"FAILED: {result['error']}")
        sys.exit(1)
    
    if result.get("status") == "success":
        print("SUCCESS: Fetched deployment logs from S3.")
        print(f"Source: {result.get('source')}")
        print("Data Preview:")
        # Print a snippet of the data
        config = result.get('deployment_data', {})
        print(f"  Repo: {config.get('repository', {}).get('full_name')}")
        print(f"  Commits: {len(config.get('commits', []))}")
        print(f"  Head Commit: {config.get('head_commit', {}).get('message')}")
    else:
        print(f"FAILED: Unexpected response structure: {result}")
        sys.exit(1)

def test_agent_definition():
    print("\nVerifying Agent definition...")
    tools = [tool.__name__ for tool in deploy_agent.tools]
    print(f"Agent Name: {deploy_agent.name}")
    print(f"Tools: {tools}")
    
    if "fetch_deployment_logs" not in tools:
        print("FAILED: fetch_deployment_logs not found in agent tools.")
        sys.exit(1)
    
    if "analyze_deployments" in tools:
        print("FAILED: Old tool 'analyze_deployments' still present.")
        sys.exit(1)
        
    print("SUCCESS: Agent definition looks correct.")

if __name__ == "__main__":
    test_s3_fetch()
    test_agent_definition()
