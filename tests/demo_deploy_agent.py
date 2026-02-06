import json
import datetime
from app.agents.deploy_agent import analyze_deployments

def demo_deploy_agent():
    print("=== Deploy Agent Live Demo ===\n")
    
    # Analyze the last 2 hours of this repository
    now = datetime.datetime.now(datetime.timezone.utc)
    time_window = {
        "start": (now - datetime.timedelta(hours=2)).isoformat(),
        "end": now.isoformat(),
        "incident_id": "INC-DEMO-LIVE"
    }
    
    service = "checkout-service"
    # We'll use the current time as the "anomaly start" to see how it correlates
    anomaly_start = now.isoformat()
    
    print(f"Analyzing deployments for '{service}' in the last 2 hours...")
    result = analyze_deployments(service, time_window, anomaly_start=anomaly_start)
    
    print("\n--- Final Summary ---")
    print(result.get("summary", "No summary generated"))
    
    if result["findings"]:
        print("\n--- Recent Commits Found ---")
        for f in result["findings"]:
            print(f"- {f['deploy_id']} | Score: {f['correlation_score']} | Author: {f['author']}")
            print(f"  Message: {f['message']}")
            if f['affected_files']:
                print(f"  Files: {', '.join(f['affected_files'][:3])}")
            print()

if __name__ == "__main__":
    demo_deploy_agent()
