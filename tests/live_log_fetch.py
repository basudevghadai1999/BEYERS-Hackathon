import json
from app.tools.cloudwatch_logs import query_logs_insights
import datetime
import os

def test_live_fetch():
    service = "checkout-service"
    # Using a 10-minute window as requested
    now = datetime.datetime.now(datetime.timezone.utc)
    time_window = {
        "start": (now - datetime.timedelta(minutes=10)).isoformat(),
        "end": now.isoformat(),
        "incident_id": "INC-LIVE-10MIN"
    }
    
    print(f"Fetching logs for {service} from {time_window['start']} to {time_window['end']}...")
    
    try:
        results = query_logs_insights(service, time_window)
        print(f"Successfully fetched {len(results)} matches.")
        if results:
            print("\nSample Log Entry:")
            print(json.dumps(results[0], indent=2))
        else:
            print("No logs found in the specified window.")
    except Exception as e:
        print(f"Error fetching logs: {e}")

if __name__ == "__main__":
    # Ensure region is set if not already in env
    if "AWS_DEFAULT_REGION" not in os.environ:
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    test_live_fetch()
