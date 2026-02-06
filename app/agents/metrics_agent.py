from google.adk import Agent
from app.tools.cloudwatch_metrics import get_metric_data
from app.tools.anomaly_detector import detect_anomalies
from app.tools.envelope import build_response_envelope
import datetime

def query_metrics_and_detect_anomalies(service: str, metric_names: list, time_window: dict, threshold: float = 2.0) -> dict:
    """
    Fetches metrics and detects anomalies. Returns findings for the agent to analyze.
    """
    start_time = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Fetch data
    try:
        raw_data = get_metric_data(service, metric_names, time_window)
    except Exception as e:
        return {"error": str(e)}
    
    # 2. Extract findings
    anomalies_detected = []
    for m_name, datapoints in raw_data.items():
        analysis = detect_anomalies(datapoints, threshold=threshold)
        if analysis["anomalies"]:
            # Basic stats for the LLM to use
            peak_val = max(d["value"] for d in datapoints)
            base_val = analysis["baseline_mean"]
            change_factor = peak_val / base_val if base_val > 0 else 0
            
            anomalies_detected.append({
                "metric_name": m_name,
                "anomaly_start": analysis["anomalies"][0]["timestamp"],
                "baseline_avg": base_val,
                "peak_value": peak_val,
                "change_factor": change_factor,
                "raw_datapoints": datapoints[-5:] # Context for LLM
            })
            
    return {
        "anomalies": anomalies_detected,
        "count": len(anomalies_detected),
        "service": service,
        "incident_id": time_window.get("incident_id", "INC-UNKNOWN")
    }

def submit_metrics_response(incident_id: str, findings: list, summary: str) -> dict:
    """
    Submits the final response with the agent's generated summary.
    """
    start_time = datetime.datetime.now(datetime.timezone.utc) # Approx start for envelope
    return build_response_envelope(
        agent_name="metrics_agent",
        incident_id=incident_id,
        findings=findings,
        start_time=start_time,
        summary=summary
    )

metrics_agent = Agent(
    name="metrics_agent",
    model="bedrock/us.anthropic.claude-opus-4-5-20251101-v1:0",
    description="Analyzes CloudWatch metrics to identify anomalies and degradation trends.",
    instruction="""
    You are the Metrics Intelligence Agent. Your task is to:
    1. Call `query_metrics_and_detect_anomalies` to fetch data.
    2. Analyze the returned 'anomalies' and 'raw_datapoints'.
    3. Determine the trend (rising, recovering, stable) and severity based on the data.
    4. Generate a concise, expert summary of the situation (e.g., "Critical latency spike detected...").
    5. Call `submit_metrics_response` with the original extracted findings and your generated summary.
    """,
    tools=[query_metrics_and_detect_anomalies, submit_metrics_response]
)
