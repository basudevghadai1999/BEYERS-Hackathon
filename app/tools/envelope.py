import datetime


def build_response_envelope(
    agent_name: str,
    incident_id: str,
    findings: list,
    start_time: datetime.datetime,
    error: str = None,
    summary: str = None,
) -> dict:
    """
    Standard response wrapper for all agents.
    """
    end_time = datetime.datetime.now(datetime.timezone.utc)
    execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

    if error:
        status = "failed"
    else:
        status = "completed" if findings else "no_findings"

    # Default summary if not provided
    if not summary:
        if error:
            summary = f"Agent execution failed: {error}"
        elif findings:
            summary = f"Agent found {len(findings)} anomalies/issues."
        else:
            summary = "No anomalies or significant issues detected."

    response = {
        "agent": agent_name,
        "incident_id": incident_id,
        "timestamp": end_time.isoformat(),
        "status": status,
        "findings": findings,
        "summary": summary,
        "metadata": {
            "execution_time_ms": execution_time_ms,
            "findings_count": len(findings),
        },
    }

    if error:
        response["error"] = error

    return response
