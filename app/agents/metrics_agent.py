from google.adk import Agent
from app.tools.cloudwatch_metrics import get_metric_data
from app.tools.anomaly_detector import detect_anomalies
from app.tools.envelope import build_response_envelope
import datetime

def query_metrics_and_detect_anomalies(service: str, metric_names: list, time_window: dict, threshold: float = 2.0) -> dict:
    """
    Combines fetching metrics and detecting anomalies into a single tool for the agent.
    """
    start_time = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Fetch data
    try:
        raw_data = get_metric_data(service, metric_names, time_window)
    except Exception as e:
        # Graceful handling for API failures
        return build_response_envelope(
            agent_name="metrics_agent",
            incident_id=time_window.get("incident_id", "INC-UNKNOWN"),
            findings=[],
            start_time=start_time,
            error=str(e)
        )
    
    # 2. Extract findings
    anomalies_detected = []
    for m_name, datapoints in raw_data.items():
        analysis = detect_anomalies(datapoints, threshold=threshold)
        if analysis["anomalies"]:
            # Simple summary for the anomaly
            peak_val = max(d["value"] for d in datapoints)
            base_val = analysis["baseline_mean"]
            change_factor = peak_val / base_val if base_val > 0 else 0
            
            trend = "stable"
            if len(datapoints) > 1:
                if datapoints[-1]["value"] > datapoints[-2]["value"]:
                    trend = "rising"
                elif datapoints[-1]["value"] < datapoints[-2]["value"]:
                    trend = "recovering"
                else:
                    trend = "saturated"
            
            anomalies_detected.append({
                "metric_name": m_name,
                "anomaly_start": analysis["anomalies"][0]["timestamp"],
                "baseline_avg": base_val,
                "peak_value": peak_val,
                "change_factor": change_factor,
                "trend": trend
            })
            
    # 3. Generate Smart Summary
    summary = None
    if anomalies_detected:
        critical_alerts = []
        start_times = {}
        for a in anomalies_detected:
            # Group by start time (rounded to minutes)
            ts = a["anomaly_start"][:16]
            start_times[ts] = start_times.get(ts, 0) + 1
            
            if "latency" in a["metric_name"].lower() and a["peak_value"] > 2000:
                critical_alerts.append(f"Critical: {a['metric_name']} spiked to {a['peak_value']:.2f}ms (threshold 2000ms exceeded).")
            else:
                critical_alerts.append(f"{a['metric_name']} showed a {a['change_factor']:.1f}x increase compared to baseline.")
        
        # Add correlation summary if multiple anomalies share a start time
        correlation_note = ""
        top_ts = max(start_times, key=start_times.get) if start_times else None
        if top_ts and start_times[top_ts] > 1:
            correlation_note = f" Correlation: {start_times[top_ts]} anomalies start at {top_ts}."
            
        summary = " ".join(critical_alerts) + correlation_note
            
    # 4. Build envelope
    return build_response_envelope(
        agent_name="metrics_agent",
        incident_id=time_window.get("incident_id", "INC-UNKNOWN"),
        findings=anomalies_detected,
        start_time=start_time,
        summary=summary
    )

metrics_agent = Agent(
    name="metrics_agent",
    description="Analyzes CloudWatch metrics to identify anomalies and degradation trends.",
    instruction="""
    You are the Metrics Intelligence Agent. Your task is to:
    1. Fetch metrics for the specified service and time window.
    2. Identify anomalies in the metrics using z-score analysis.
    3. Compute change factors (peak vs. baseline) and determine trends (rising, saturated, recovering).
    4. Correlate anomalies across different metrics to identify possible root causes (e.g., CPU spike coinciding with latency).
    5. Return a structured response using the standard envelope.
    """,
    tools=[query_metrics_and_detect_anomalies]
)
