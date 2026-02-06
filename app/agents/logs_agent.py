from google.adk import Agent
from app.tools.cloudwatch_logs import query_logs_insights
from app.tools.stack_parser import extract_stack_traces
from app.tools.envelope import build_response_envelope
import datetime

def analyze_logs(service: str, time_window: dict, filter_pattern: str = None) -> dict:
    """
    Fetches logs, summarizes errors, and extracts stack traces.
    """
    start_time = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Fetch logs
    try:
        logs = query_logs_insights(service, time_window, filter_pattern)
    except Exception as e:
        return build_response_envelope(
            agent_name="logs_agent",
            incident_id=time_window.get("incident_id", "INC-UNKNOWN"),
            findings=[],
            start_time=start_time,
            error=str(e)
        )
        
    # 2. Extract findings
    error_summary = {}
    sample_entries = []
    
    for entry in logs:
        error_code = entry.get("error_code", "UNKNOWN_ERROR")
        if error_code not in error_summary:
            error_summary[error_code] = {
                "count": 0,
                "first_seen": entry.get("@timestamp"),
                "last_seen": entry.get("@timestamp")
            }
        
        error_summary[error_code]["count"] += 1
        error_summary[error_code]["last_seen"] = entry.get("@timestamp")
        
        # Extract stack trace for high priority errors
        if len(sample_entries) < 3:
            parsed_stack = extract_stack_traces(entry)
            if parsed_stack:
                entry["parsed_stack_trace"] = parsed_stack
                sample_entries.append(entry)
                
    findings = {
        "matched_entries": len(logs),
        "error_summary": error_summary,
        "sample_entries": sample_entries
    }
    
    # 3. Generate Smart Summary
    summary = None
    if logs:
        top_errors = sorted(error_summary.items(), key=lambda x: x[1]["count"], reverse=True)[:2]
        error_descriptions = [f"{count_info['count']}x {code}" for code, count_info in top_errors]
        summary = f"Detected {len(logs)} error logs. Top issues: {', '.join(error_descriptions)}."
    
    # 4. Build envelope
    return build_response_envelope(
        agent_name="logs_agent",
        incident_id=time_window.get("incident_id", "INC-UNKNOWN"),
        findings=[findings] if logs else [],
        start_time=start_time,
        summary=summary
    )

logs_agent = Agent(
    name="logs_agent",
    description="Reads and analyzes CloudWatch Logs to identify errors and stack traces.",
    instruction="""
    You are the Logs Intelligence Agent. Your task is to:
    1. Query CloudWatch Logs Insights for the service and time window.
    2. Focus on ERROR, FATAL, and WARN levels.
    3. Summarize occurrences of different error codes (e.g., DB_CONN_TIMEOUT).
    4. Extract and parse stack traces to identify the root cause frame.
    5. Return a structured response using the standard envelope.
    """,
    tools=[analyze_logs]
)
