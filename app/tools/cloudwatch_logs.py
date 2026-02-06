import boto3
import time
from typing import List, Dict, Optional

def query_logs_insights(service: str, time_window: Dict[str, str], filter_pattern: Optional[str] = None) -> List[Dict]:
    """
    Queries CloudWatch Logs Insights for a given service and time window.
    """
    logs_client = boto3.client("logs")
    
    import datetime
    start_time = int(datetime.datetime.fromisoformat(time_window["start"].replace("Z", "+00:00")).timestamp())
    end_time = int(datetime.datetime.fromisoformat(time_window["end"].replace("Z", "+00:00")).timestamp())
    
    log_group = f"/bayer/{service}"
    
    query = (
        "fields @timestamp, @message, level, error_code, stack_trace "
        "| filter level in ['ERROR', 'FATAL', 'WARN'] "
    )
    if filter_pattern:
        query += f"| filter @message like /{filter_pattern}/ "
    
    query += "| sort @timestamp asc | limit 50"
    
    start_query_response = logs_client.start_query(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        queryString=query,
    )
    
    query_id = start_query_response["queryId"]
    
    response = None
    while response is None or response["status"] == "Running":
        time.sleep(1)
        response = logs_client.get_query_results(queryId=query_id)
        
    results = []
    for result in response.get("results", []):
        entry = {item["field"]: item["value"] for item in result}
        results.append(entry)
        
    return results
