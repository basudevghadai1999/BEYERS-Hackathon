import json
from app.agents.metrics_agent import query_metrics_and_detect_anomalies
import datetime
import os

def test_live_metrics_fetch():
    service = "checkout-service"
    metric_names = ["p99_latency_ms"]
    
    # Using a 10-minute window as requested
    now = datetime.datetime.now(datetime.timezone.utc)
    time_window = {
        "start": (now - datetime.timedelta(minutes=10)).isoformat(),
        "end": now.isoformat(),
        "incident_id": "INC-LIVE-10MIN"
    }
    
    print(f"Fetching metrics for {service} from {time_window['start']} to {time_window['end']}...")
    
    try:
        # Mocking or calling actual helper to see raw counts
        from app.tools.cloudwatch_metrics import get_metric_data
        raw = get_metric_data(service, metric_names, time_window)
        for m, pts in raw.items():
            print(f"Found {len(pts)} datapoints for {m}")
            if pts:
                vals = [p['value'] for p in pts]
                print(f"Values: {vals}")

        # This will call the actual get_metric_data and detect_anomalies
        result = query_metrics_and_detect_anomalies(service, metric_names, time_window, threshold=1.0)
        
        print(f"Agent Status: {result['status']}")
        print(f"Summary: {result.get('summary', 'No summary generated')}")
        
        if result['findings']:
            print("\nAnomalies Detected:")
            for finding in result['findings']:
                print(f"- Metric: {finding['metric_name']}")
                print(f"  Peak: {finding['peak_value']}")
                print(f"  Change Factor: {finding['change_factor']:.2f}")
                print(f"  Trend: {finding['trend']}")
        else:
            print("\nNo anomalies detected in the live stream.")
            
    except Exception as e:
        print(f"Error executing agent tool: {e}")

if __name__ == "__main__":
    if "AWS_DEFAULT_REGION" not in os.environ:
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    test_live_metrics_fetch()
