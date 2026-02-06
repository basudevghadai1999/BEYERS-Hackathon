import subprocess
import datetime
from typing import List, Dict

def get_github_deployments(service: str, time_window: dict) -> List[Dict]:
    """
    Fetches git commits from the local repository within the specified time window.
    Heuristically filters for relevant service if provided.
    """
    # Convert window to datetime for comparison
    start_time = datetime.datetime.fromisoformat(time_window["start"].replace("Z", "+00:00"))
    end_time = datetime.datetime.fromisoformat(time_window["end"].replace("Z", "+00:00"))

    # 1. Fetch hashes and dates for commits in the window
    try:
        cmd = ["git", "log", "--pretty=format:%H|%ad", "--date=iso-strict"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_log = result.stdout.strip()
    except Exception as e:
        raise Exception(f"Error fetching git log: {e}")

    if not raw_log:
        return []

    relevant_hashes = []
    for line in raw_log.split("\n"):
        if "|" not in line: continue
        chash, date_str = line.split("|")
        commit_date = datetime.datetime.fromisoformat(date_str)
        if start_time <= commit_date <= end_time:
            relevant_hashes.append(chash)

    deployments = []
    # 2. For each relevant commit, fetch full details
    for chash in relevant_hashes:
        try:
            # %H: hash, %an: author, %ad: author date, %s: subject, %b: body
            show_cmd = ["git", "show", "--pretty=format:%H|%an|%ad|%s|%b", "--date=iso-strict", "--name-only", chash]
            show_result = subprocess.run(show_cmd, capture_output=True, text=True, check=True)
            show_output = show_result.stdout.strip()
            
            lines = show_output.split("\n")
            if not lines: continue
            
            meta = lines[0]
            parts = meta.split("|", 4)
            if len(parts) < 5: continue
            
            _, author, date_str, subject, body = parts
            
            # Remaining lines are filenames (after the body)
            # Find where filenames start (after the first blank line following the metadata)
            files = []
            for line in lines[1:]:
                line = line.strip()
                if not line: continue
                # In 'git show --name-only', files appear at the end
                if "." in line and "/" in line:
                    files.append(line)
            
            full_message = f"{subject}\n{body}"
            
            if service and service.lower() not in full_message.lower() and service.lower() not in "checkout-service":
                continue

            deployments.append({
                "deploy_id": chash[:8],
                "timestamp": date_str,
                "author": author,
                "message": subject,
                "full_details": full_message,
                "affected_files": files,
                "service": service or "unknown"
            })
        except Exception as e:
            print(f"Error fetching details for {chash}: {e}")
            continue

    return deployments
