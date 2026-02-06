import boto3
import json
import datetime

def upload_mock_data():
    """Uploads a mock GitHub push event to S3."""
    bucket_name = "bucketrag-426313057150"
    
    # Mock GitHub Push Event Data
    mock_push_event = {
        "ref": "refs/heads/main",
        "before": "a8dcb82424",
        "after": "f84b140888",
        "repository": {
            "name": "BEYERS-Hackathon",
            "full_name": "basudevghadai1999/BEYERS-Hackathon",
            "owner": {
                "name": "basudevghadai1999",
                "email": "basudev@example.com"
            },
            "html_url": "https://github.com/basudevghadai1999/BEYERS-Hackathon",
            "description": "Hackathon project"
        },
        "pusher": {
            "name": "basudevghadai1999",
            "email": "basudev@example.com"
        },
        "commits": [
            {
                "id": "f84b140888",
                "tree_id": "cf7afdd...",
                "distinct": True,
                "message": "fix: populate empty Dockerfile for Lambda",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "url": "https://github.com/basudevghadai1999/BEYERS-Hackathon/commit/f84b140888",
                "author": {
                    "name": "Basudev",
                    "email": "basudev@example.com",
                    "username": "basudevghadai1999"
                },
                "committer": {
                    "name": "Basudev",
                    "email": "basudev@example.com",
                    "username": "basudevghadai1999"
                },
                "added": ["Dockerfile"],
                "removed": [],
                "modified": []
            },
            {
                "id": "a8dcb82424",
                "tree_id": "f84b140...",
                "distinct": True,
                "message": "feat: trigger Lambda update on deploy",
                "timestamp": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)).isoformat(),
                "url": "https://github.com/basudevghadai1999/BEYERS-Hackathon/commit/a8dcb82424",
                "author": {
                    "name": "Basudev",
                    "email": "basudev@example.com",
                    "username": "basudevghadai1999"
                },
                "committer": {
                    "name": "Basudev",
                    "email": "basudev@example.com",
                    "username": "basudevghadai1999"
                },
                "added": [],
                "removed": [],
                "modified": [".github/workflows/deploy.yml"]
            }
        ],
        "head_commit": {
            "id": "f84b140888",
            "tree_id": "cf7afdd...",
            "distinct": True,
            "message": "fix: populate empty Dockerfile for Lambda",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "url": "https://github.com/basudevghadai1999/BEYERS-Hackathon/commit/f84b140888",
            "author": {
                "name": "Basudev",
                "email": "basudev@example.com",
                "username": "basudevghadai1999"
            },
            "committer": {
                "name": "Basudev",
                "email": "basudev@example.com",
                "username": "basudevghadai1999"
            },
            "added": ["Dockerfile"],
            "removed": [],
            "modified": []
        }
    }

    s3 = boto3.client("s3")
    key = "mock_github_push_event.json"
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(mock_push_event, indent=2),
            ContentType="application/json"
        )
        print(f"Successfully uploaded mock GitHub push event to s3://{bucket_name}/{key}")
    except Exception as e:
        print(f"Failed to upload mock push event: {str(e)}")

if __name__ == "__main__":
    upload_mock_data()
