from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from app.tools.envelope import build_response_envelope
import datetime
import boto3
import json


def fetch_deployment_logs():
    """Fetches deployment logs (mock GitHub push event) from S3."""
    bucket_name = "bucketrag-426313057150"
    key = "mock_github_push_event.json"
    s3 = boto3.client("s3")
    
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return {
            "source": f"s3://{bucket_name}/{key}",
            "deployment_data": data,
            "status": "success"
        }
    except Exception as e:
        return {"error": f"Failed to fetch deployment logs from S3: {str(e)}"}


def submit_deploy_response(incident_id: str, findings: list, summary: str) -> dict:
    """Submits the final response with the agent's generated summary."""
    start_time = datetime.datetime.now(datetime.timezone.utc)
    return build_response_envelope(
        agent_name="deploy_agent",
        incident_id=incident_id,
        findings=findings,
        start_time=start_time,
        summary=summary,
    )


deploy_agent = Agent(
    name="deploy_agent",
    model=LiteLlm(model="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0"),
    description="Analyzes deployment logs from S3 to identify potential causes of incidents.",
    instruction="""You are the Deployment Intelligence Agent. When you receive a task:
1. Call `fetch_deployment_logs` to retrieve the latest deployment information from S3.
2. Analyze the 'deployment_data' in the response. Look at the 'commits' list, 'pusher', and 'repository' details.
3. Identify any risky changes (e.g., modified files, commit messages indicating fixes or features).
4. Generate a professional summary (e.g., "Analyzed deployment logs from S3. Found push event [ref] by [pusher]. Commit [id]: [message] modified [files]...").
5. Call `submit_deploy_response` with a list formatted as findings (can be the raw commits list or a simplified version) and your summary.
6. After responding, you will automatically return control to the Commander.
""",
    tools=[fetch_deployment_logs, submit_deploy_response],
    output_key="deploy_findings",
)
