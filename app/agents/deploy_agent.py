from google.adk import Agent
from app.tools.github_deployments import get_github_deployments
from app.tools.deploy_correlator import correlate_deploy_to_incident
from app.tools.envelope import build_response_envelope
import datetime

def analyze_deployments(service: str, time_window: dict, anomaly_start: str = None) -> dict:
    """
    Fetches GitHub commits and correlates them with the incident.
    """
    start_time = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Fetch deployments from GitHub
    try:
        deployments = get_github_deployments(service, time_window)
    except Exception as e:
        return build_response_envelope(
            agent_name="deploy_agent",
            incident_id=time_window.get("incident_id", "INC-UNKNOWN"),
            findings=[],
            start_time=start_time,
            error=str(e)
        )
        
    # 2. Correlate
    # Use incident detection time if anomaly_start is not provided
    ref_time = anomaly_start or time_window["end"]
    correlation_results = correlate_deploy_to_incident(deployments, ref_time)
    
    # 3. Generate Detailed Smart Summary
    summary = None
    if correlation_results["highest_risk_deploy"]:
        top = correlation_results["highest_risk_deploy"]
        
        # Extract change details from message and files
        change_desc = top['full_details'].split("\n")[0] # Subject
        files_str = ", ".join(top['affected_files'][:3])
        if len(top['affected_files']) > 3:
            files_str += f", and {len(top['affected_files']) - 3} more"
            
        summary = (
            f"Last deployment identified: '{change_desc}' by **{top['author']}**. "
            f"Service: **{top['service']}**. "
            f"Configuration Changes: {('Files: ' + files_str) if files_str else 'No specific config files detected in commit.'}. "
            f"Correlation score: {top['correlation_score']}."
        )
        
        if top["correlation_score"] >= 0.7:
             summary = "🚨 " + summary
    else:
        summary = "No recent deployments found in the specified time window."
        
    # 4. Build envelope
    return build_response_envelope(
        agent_name="deploy_agent",
        incident_id=time_window.get("incident_id", "INC-UNKNOWN"),
        findings=correlation_results["correlations"],
        start_time=start_time,
        summary=summary
    )

deploy_agent = Agent(
    name="deploy_agent",
    description="Analyzes GitHub commit history to identify risky deployments related to an incident.",
    instruction="""
    You are the Deployment Intelligence Agent. Your task is to:
    1. Retrieve recent commits (deployments) from GitHub for the affected service.
    2. Correlate these changes with the incident timing and reported errors.
    3. Identify the highest-risk change (e.g., config changes, DB migrations).
    4. Return a structured response identifying the 'risky' commit if found.
    """,
    tools=[analyze_deployments]
)
