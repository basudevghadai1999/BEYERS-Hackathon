# Agent Tools Reference — Build Guide

> **Audience:** Developer assigned to implement all Lambda-based tools.
> **Rule:** Every tool is a single Python function inside a Lambda handler. Keep them pure — data in, findings out. No LLM calls except in the Commander.

---

## Quick Reference — All Tools

| # | Tool Name | Owner Agent | AWS Dependencies | Priority |
|---|-----------|-------------|------------------|----------|
| 1 | `parse_alarm_event` | Shared / Commander | — | P0 |
| 2 | `invoke_bedrock` | Commander | Bedrock | P0 |
| 3 | `save_state` | Shared | DynamoDB | P0 |
| 4 | `load_state` | Shared | DynamoDB | P0 |
| 5 | `scan_logs` | Logs Agent | S3 | P0 |
| 6 | `extract_stack_traces` | Logs Agent | — | P1 |
| 7 | `query_metrics` | Metrics Agent | S3 | P0 |
| 8 | `detect_anomalies` | Metrics Agent | — | P1 |
| 9 | `get_deployments` | Deploy Intel Agent | S3 | P0 |
| 10 | `correlate_deploy_to_incident` | Deploy Intel Agent | — | P1 |
| 11 | `generate_rca_report` | Report Generator | S3 | P0 |
| 12 | `send_notification` | Report Generator | SNS | P1 |
| 13 | `build_response_envelope` | Shared | — | P0 |

---

## Shared Tools (used by multiple agents)

---

### Tool 1: `parse_alarm_event`

**Purpose:** Extracts structured incident context from the raw CloudWatch/EventBridge alarm event.

**File:** `lambdas/shared/event_parser.py`

```
Input (raw EventBridge event):
{
  "detail": {
    "alarmName": "checkout-service-p99-latency-critical",
    "state": { "value": "ALARM", "reason": "...", "timestamp": "..." },
    "previousState": { "value": "OK", "timestamp": "..." },
    "configuration": { "metrics": [...] }
  }
}

Output:
{
  "incident_id": "INC-20260206-143000",      # generated: INC-<date>-<HHmmss>
  "service": "checkout-service",               # parsed from alarmName
  "metric_name": "p99_latency_ms",             # from configuration.metrics
  "threshold": 2000.0,                         # from alarm reason
  "current_values": [2100.0, 2300.0],          # from reasonData
  "alarm_state": "ALARM",
  "previous_state": "OK",
  "detected_at": "2026-02-06T14:30:00Z",
  "region": "us-east-1"
}
```

**Implementation Notes:**
- Parse `alarmName` to extract service name (split on first `-` segments before `-p99` or `-error`)
- Parse `reasonData` (it's a JSON string inside JSON — needs double-decode)
- Generate `incident_id` from timestamp: `INC-YYYYMMDD-HHmmss`

---

### Tool 2: `save_state`

**Purpose:** Writes an entity to the DynamoDB `AIC-IncidentState` table.

**File:** `lambdas/shared/state_store.py`

```
Input:
{
  "incident_id": "INC-20260206-143000",
  "entity_type": "FINDING#logs",            # SK prefix
  "data": { ... }                           # arbitrary payload
}

Behavior:
- PK = "INCIDENT#INC-20260206-143000"
- SK = "FINDING#logs#2026-02-06T14:31:00Z"  # entity_type + current timestamp
- Merges `data` as top-level attributes
- Adds `created_at` automatically

DynamoDB call:
  table.put_item(Item={PK, SK, **data, created_at})
```

**Implementation Notes:**
- Use `boto3.resource("dynamodb")` for cleaner API
- Table name from env var `STATE_TABLE_NAME`
- Timestamp in SK ensures sort order

---

### Tool 3: `load_state`

**Purpose:** Reads entities from the DynamoDB table for a given incident.

**File:** `lambdas/shared/state_store.py` (same file as save_state)

```
Input:
{
  "incident_id": "INC-20260206-143000",
  "entity_prefix": "FINDING#",              # optional — SK begins_with filter
  "limit": 10                               # optional — default all
}

Output:
[
  { "SK": "FINDING#logs#...", "severity": "critical", ... },
  { "SK": "FINDING#metrics#...", "anomaly_score": 0.95, ... },
  ...
]

DynamoDB call:
  table.query(
    KeyConditionExpression=Key("PK").eq(...) & Key("SK").begins_with(prefix),
    ScanIndexForward=True
  )
```

---

### Tool 4: `build_response_envelope`

**Purpose:** Every agent wraps its output in a standard envelope before returning to Step Functions.

**File:** `lambdas/shared/envelope.py`

```python
def build_response_envelope(agent_name: str, incident_id: str, findings: list) -> dict:
    """
    Returns:
    {
      "agent": "logs_agent",
      "incident_id": "INC-20260206-143000",
      "timestamp": "2026-02-06T14:31:22Z",   # auto-generated
      "status": "completed",
      "findings": [ ... ],
      "metadata": {
        "execution_time_ms": 340,             # auto-calculated
        "findings_count": 3
      }
    }
    """
```

**Implementation Notes:**
- Capture `start_time` at handler entry, compute delta at exit
- If `findings` is empty, set `status` to `"no_findings"`
- This is a plain function, not a Lambda — imported by all agents

---

## Commander Agent Tools

---

### Tool 5: `invoke_bedrock`

**Purpose:** Sends a prompt to Amazon Bedrock and returns the parsed response. Used in both PLAN and DECIDE phases.

**File:** `lambdas/commander/bedrock_client.py`

```
Input:
{
  "phase": "plan",                           # "plan" or "decide"
  "system_prompt": "You are an SRE ...",
  "user_prompt": "Analyze this alarm ...",
  "response_schema": { ... }                 # optional JSON schema for structured output
}

Output (for phase=plan):
{
  "investigation_plan": {
    "hypothesis": "Possible DB connection issue caused by recent config change",
    "steps": [
      { "agent": "logs_agent", "task": "Search for DB_CONN_TIMEOUT errors in checkout-service between 14:00-14:35" },
      { "agent": "metrics_agent", "task": "Check p99_latency, db_connection_pool_active, cpu for checkout-service" },
      { "agent": "deploy_agent", "task": "Find all deployments to checkout-service in the last 2 hours" }
    ],
    "priority_service": "checkout-service",
    "time_window": { "start": "2026-02-06T14:00:00Z", "end": "2026-02-06T14:35:00Z" }
  }
}

Output (for phase=decide):
{
  "root_cause": "Config deployment deploy-20260206-1400 reduced DB pool max_connections from 100 to 50...",
  "confidence": 0.95,
  "evidence_chain": [ ... ],
  "recommended_action": "rollback",
  "rollback_target": { "service": "checkout-service", "version": "3.8.0" }
}
```

**Implementation Notes:**
- Use `boto3.client("bedrock-runtime")` with `invoke_model`
- Model ID: `anthropic.claude-sonnet-4-5-20250929-v1:0` (or whichever is available in your region)
- Set `max_tokens: 2048` for plan, `4096` for decide
- Use Bedrock's tool_use / JSON mode to enforce `response_schema` — avoids hallucination
- **Retry with exponential backoff** on `ThrottlingException`
- Env vars: `BEDROCK_MODEL_ID`, `BEDROCK_REGION`

**System Prompt Templates:**

```
PLAN phase system prompt:
"You are an expert SRE incident commander. Given a CloudWatch alarm event, generate
an investigation plan. Output JSON only. Identify which agents to dispatch and what
specific data each should look for. Always include a time window and hypothesis."

DECIDE phase system prompt:
"You are an expert SRE incident commander. You are given findings from three
investigation agents (logs, metrics, deployments). Correlate the evidence, determine
the root cause, assign a confidence score (0.0–1.0), and recommend an action.
If confidence >= 0.8, recommend 'rollback' with the target version.
If confidence < 0.8, recommend 'escalate' to human on-call."
```

---

## Logs Agent Tools

---

### Tool 6: `scan_logs`

**Purpose:** Reads mock log files from S3 for a given service and time range. Filters by level and error pattern.

**File:** `lambdas/logs_agent/handler.py`

```
Input (from Step Functions):
{
  "incident_id": "INC-20260206-143000",
  "service": "checkout-service",
  "time_window": { "start": "2026-02-06T14:00:00Z", "end": "2026-02-06T14:35:00Z" },
  "filters": {
    "levels": ["ERROR", "FATAL", "WARN"],
    "error_codes": []                        # empty = all errors
  }
}

Output:
{
  "matched_entries": 14,
  "error_summary": {
    "DB_CONN_TIMEOUT": { "count": 7, "first_seen": "2026-02-06T14:20:01Z", "last_seen": "2026-02-06T14:34:55Z" },
    "DB_POOL_EXHAUSTED": { "count": 1, "first_seen": "2026-02-06T14:18:33Z" },
    "CIRCUIT_BREAKER_OPEN": { "count": 1, "first_seen": "2026-02-06T14:24:00Z" },
    "ORDER_PROCESSING_FAILED": { "count": 1, "first_seen": "2026-02-06T14:23:15Z" },
    "CASCADING_FAILURE": { "count": 1, "first_seen": "2026-02-06T14:32:11Z" },
    "HEALTH_CHECK_FAIL": { "count": 1, "first_seen": "2026-02-06T14:31:05Z" }
  },
  "dominant_error": "DB_CONN_TIMEOUT",
  "sample_entries": [ <first 3 ERROR entries with full stack traces> ]
}
```

**Implementation Notes:**
- S3 key pattern: `logs/{service}/{time_file}.json` where `time_file` = `2026-02-06T14-00`
- Convert `time_window.start` → list of S3 keys that fall in range (e.g., `T14-00`, `T14-15`, `T14-20`, `T14-30`)
- Read each file, parse JSON array, filter by `level` and optional `error_codes`
- Group by `error_code`, count occurrences, find `first_seen` / `last_seen`
- Keep only 3 sample entries to stay under Step Functions 256KB payload limit
- Env var: `MOCK_DATA_BUCKET`

---

### Tool 7: `extract_stack_traces`

**Purpose:** Parses stack traces from log entries and extracts the top frame (root cause location).

**File:** `lambdas/logs_agent/stack_parser.py`

```
Input:
{
  "stack_trace": "com.bayer.checkout.db.ConnectionPool.acquire(ConnectionPool.java:142)\n  at ..."
}

Output:
{
  "root_frame": {
    "class": "ConnectionPool",
    "method": "acquire",
    "file": "ConnectionPool.java",
    "line": 142
  },
  "call_chain": ["ConnectionPool.acquire", "ConnectionManager.getConnection", "OrderRepository.save", "OrderService.processOrder"],
  "depth": 4
}
```

**Implementation Notes:**
- Regex: `(\w[\w.]*)\((\w+\.java):(\d+)\)`
- First match = root frame (deepest cause)
- This is a pure utility function — no AWS calls

---

## Metrics Agent Tools

---

### Tool 8: `query_metrics`

**Purpose:** Reads mock time-series metrics from S3 for a given service.

**File:** `lambdas/metrics_agent/handler.py`

```
Input (from Step Functions):
{
  "incident_id": "INC-20260206-143000",
  "service": "checkout-service",
  "metric_names": ["p99_latency_ms", "cpu_utilization_percent", "db_connection_pool_active", "db_connection_wait_queue", "error_rate_percent"],
  "time_window": { "start": "2026-02-06T14:00:00Z", "end": "2026-02-06T14:35:00Z" }
}

Output:
{
  "metrics_analyzed": 5,
  "anomalies_detected": [
    {
      "metric_name": "p99_latency_ms",
      "anomaly_start": "2026-02-06T14:15:00Z",
      "baseline_avg": 183.0,
      "peak_value": 2300.0,
      "change_factor": 12.6,
      "trend": "rising"
    },
    {
      "metric_name": "db_connection_pool_active",
      "anomaly_start": "2026-02-06T14:15:00Z",
      "baseline_avg": 23.0,
      "peak_value": 50.0,
      "detail": "Pool at 100% capacity (50/50) — pool_max changed from 100 to 50",
      "trend": "saturated"
    },
    ...
  ],
  "correlation": "All anomalies start at 14:15 — coincides with pool_max reduction"
}
```

**Implementation Notes:**
- S3 key: `metrics/{service}/timeseries.json`
- Read file, iterate each metric, filter datapoints to `time_window`
- Compute `baseline_avg` from non-anomaly datapoints
- Compute `peak_value` from anomaly datapoints
- `change_factor` = peak / baseline
- **Trend detection:** if last 3 anomaly values are increasing → `"rising"`, all same → `"saturated"`, decreasing → `"recovering"`
- Env var: `MOCK_DATA_BUCKET`

---

### Tool 9: `detect_anomalies`

**Purpose:** Flags datapoints as anomalies using a simple threshold/z-score method. Use this if the mock data didn't have pre-flagged `anomaly` fields (future-proofing).

**File:** `lambdas/metrics_agent/anomaly_detector.py`

```
Input:
{
  "datapoints": [ { "timestamp": "...", "value": 180 }, ... ],
  "method": "zscore",             # "zscore" or "static_threshold"
  "threshold": 2.0                # z-score threshold, or absolute value
}

Output:
{
  "anomalies": [
    { "timestamp": "2026-02-06T14:15:00Z", "value": 450, "zscore": 2.8 },
    ...
  ],
  "baseline_mean": 185.0,
  "baseline_stddev": 15.2
}
```

**Implementation Notes:**
- For z-score: compute mean/stddev from first N "stable" points, flag anything > threshold
- For static_threshold: simple `value > threshold` check
- Pure function — no AWS calls, just math

---

## Deploy Intelligence Agent Tools

---

### Tool 10: `get_deployments`

**Purpose:** Reads the deployment history from S3 and filters by service and time range.

**File:** `lambdas/deploy_agent/handler.py`

```
Input (from Step Functions):
{
  "incident_id": "INC-20260206-143000",
  "service": "checkout-service",
  "time_window": { "start": "2026-02-06T12:00:00Z", "end": "2026-02-06T14:35:00Z" },
  "include_all_services": false              # true = also show other services for context
}

Output:
{
  "deployments_found": 2,
  "deployments": [
    {
      "deploy_id": "deploy-20260206-1400",
      "timestamp": "2026-02-06T14:00:00Z",
      "service": "checkout-service",
      "version_change": "3.8.0 → 3.8.1",
      "change_summary": "Config change: tuned db-connection-pool settings...",
      "config_diff": {
        "db.pool.max_connections": { "old": 100, "new": 50 },
        "db.pool.timeout_seconds": { "old": 60, "new": 30 }
      },
      "rollback_target": "3.8.0",
      "risk_flag": "CONFIG_CHANGE_DB_POOL",
      "minutes_before_incident": 30
    },
    {
      "deploy_id": "deploy-20260206-1410",
      ...
    }
  ],
  "highest_risk_deploy": "deploy-20260206-1400"
}
```

**Implementation Notes:**
- S3 key: `deployments/deploy-history.json`
- Filter `deployments[]` where `service` matches AND `timestamp` in range
- Compute `minutes_before_incident` = incident time - deploy time
- **Risk flagging:** if `config_diff` contains keys with `pool`, `connection`, `timeout`, `memory`, `limit` → flag as high risk
- Sort by timestamp descending (most recent first)
- Env var: `MOCK_DATA_BUCKET`

---

### Tool 11: `correlate_deploy_to_incident`

**Purpose:** Scores how likely a deployment caused the incident based on timing and config changes.

**File:** `lambdas/deploy_agent/correlator.py`

```
Input:
{
  "deploy": { <single deployment record> },
  "anomaly_start": "2026-02-06T14:15:00Z",
  "dominant_error": "DB_CONN_TIMEOUT"
}

Output:
{
  "deploy_id": "deploy-20260206-1400",
  "correlation_score": 0.93,
  "reasoning": [
    "Deployed 15 minutes before anomaly start",
    "Config changed db.pool.max_connections from 100 to 50",
    "Dominant error DB_CONN_TIMEOUT is directly related to connection pool settings",
    "No other deployments to this service in the time window"
  ]
}
```

**Implementation Notes:**
- Score formula (simple weighted sum, tweak as needed):
  - `time_proximity` (0-0.3): closer to anomaly_start = higher score. 0-15min=0.3, 15-30min=0.2, 30-60min=0.1, >60min=0.0
  - `config_relevance` (0-0.4): if config_diff keys match error keywords (pool↔DB_CONN, timeout↔TIMEOUT) = 0.4
  - `has_config_change` (0-0.2): any non-empty config_diff = 0.2
  - `is_only_deploy` (0-0.1): if no other deploys in window = 0.1
- Pure function — no AWS calls

---

## Report Generator Tools

---

### Tool 12: `generate_rca_report`

**Purpose:** Assembles findings from all agents into a Markdown RCA document and uploads to S3.

**File:** `lambdas/report_generator/handler.py`

```
Input (from Step Functions — merged output of DECIDE phase):
{
  "incident_id": "INC-20260206-143000",
  "service": "checkout-service",
  "detected_at": "2026-02-06T14:30:00Z",
  "root_cause": "Config deployment deploy-20260206-1400 reduced DB pool...",
  "confidence": 0.95,
  "recommended_action": "rollback",
  "rollback_target": { "service": "checkout-service", "version": "3.8.0" },
  "logs_findings": { ... },
  "metrics_findings": { ... },
  "deploy_findings": { ... },
  "evidence_chain": [ ... ]
}

Output:
{
  "report_s3_uri": "s3://aic-reports-<acct>/INC-20260206-143000/rca.md",
  "report_url": "https://aic-reports-<acct>.s3.amazonaws.com/INC-20260206-143000/rca.md",
  "summary": "Root cause identified with 95% confidence. Rollback recommended."
}
```

**Markdown Template to Generate:**
```markdown
# Incident Report: {incident_id}

## Summary
| Field | Value |
|-------|-------|
| Incident ID | {incident_id} |
| Service | {service} |
| Detected At | {detected_at} |
| Root Cause | {root_cause} |
| Confidence | {confidence}% |
| Recommended Action | {recommended_action} |

## Timeline
- **{deploy_time}** — Deployment `{deploy_id}` applied to {service}
- **{anomaly_start}** — Anomalies begin (latency, pool exhaustion)
- **{detected_at}** — CloudWatch alarm fires
- **{report_time}** — Investigation complete

## Evidence

### Log Analysis
- Dominant error: `{dominant_error}` ({count} occurrences)
- First seen: {first_seen}
- Stack trace root: `{root_frame}`

### Metric Analysis
- p99 Latency: {baseline}ms → {peak}ms ({change_factor}x increase)
- DB Pool: {pool_baseline}/{pool_max_old} → {pool_peak}/{pool_max_new} (saturated)
- Error Rate: {error_baseline}% → {error_peak}%

### Deployment Correlation
- Deploy: `{deploy_id}` at {deploy_time}
- Change: {change_summary}
- Config diff: {config_diff}
- Correlation score: {correlation_score}

## Recommended Action
**{action}** — Roll back {service} from v{current} to v{target}

## Agent Chain of Thought
1. DETECT — Alarm received: {alarm_name}
2. PLAN — Hypothesis: {hypothesis}
3. INVESTIGATE — 3 agents dispatched in parallel
4. DECIDE — Root cause identified (confidence: {confidence})
5. ACT — {action} recommended
6. REPORT — This document generated
```

**Implementation Notes:**
- Build the markdown string using Python f-strings or `.format()`
- Upload with `s3.put_object(Bucket=..., Key=..., Body=md_string, ContentType="text/markdown")`
- Env vars: `REPORTS_BUCKET`

---

### Tool 13: `send_notification`

**Purpose:** Publishes incident summary + report link to an SNS topic.

**File:** `lambdas/report_generator/notifier.py`

```
Input:
{
  "incident_id": "INC-20260206-143000",
  "summary": "Root cause identified with 95% confidence. Rollback recommended.",
  "report_url": "https://aic-reports-<acct>.s3.amazonaws.com/...",
  "severity": "critical",
  "recommended_action": "rollback"
}

SNS Message:
{
  "default": "🚨 [CRITICAL] Incident INC-20260206-143000 — Rollback recommended. Report: <url>",
  "email": "...<formatted version>...",
  "lambda": "...<JSON payload for downstream automation>..."
}

SNS call:
  sns.publish(
    TopicArn=TOPIC_ARN,
    Subject="[AIC] CRITICAL — INC-20260206-143000 — Rollback Recommended",
    Message=json.dumps(message_structure),
    MessageStructure="json"
  )
```

**Implementation Notes:**
- Use `MessageStructure: "json"` so email/lambda/sms get different formats
- Env var: `SNS_TOPIC_ARN`

---

## Environment Variables (All Lambdas)

```
MOCK_DATA_BUCKET    = "aic-mock-data-<account-id>"
STATE_TABLE_NAME    = "AIC-IncidentState"
REPORTS_BUCKET      = "aic-reports-<account-id>"
SNS_TOPIC_ARN       = "arn:aws:sns:us-east-1:<account-id>:aic-incident-alerts"
BEDROCK_MODEL_ID    = "anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_REGION      = "us-east-1"
```

---

## IAM Permissions per Lambda

| Lambda | S3 Read | S3 Write | DynamoDB | Bedrock | SNS |
|--------|---------|----------|----------|---------|-----|
| Commander (Plan) | — | — | Read/Write | InvokeModel | — |
| Commander (Decide) | — | — | Read/Write | InvokeModel | — |
| Logs Agent | `mock-data` bucket | — | Write | — | — |
| Metrics Agent | `mock-data` bucket | — | Write | — | — |
| Deploy Agent | `mock-data` bucket | — | Write | — | — |
| Report Generator | — | `reports` bucket | Read | — | Publish |

---

## Build Order (Recommended)

```
Phase 1 — Shared (do first, everything depends on these):
  [1] build_response_envelope  → 15 min
  [2] parse_alarm_event        → 20 min
  [3] save_state / load_state  → 30 min

Phase 2 — Data Agents (can be built in parallel):
  [4] scan_logs                → 30 min
  [5] extract_stack_traces     → 15 min
  [6] query_metrics            → 30 min
  [7] detect_anomalies         → 20 min
  [8] get_deployments          → 25 min
  [9] correlate_deploy         → 20 min

Phase 3 — Brain + Output:
  [10] invoke_bedrock          → 40 min (prompt engineering takes time)
  [11] generate_rca_report     → 30 min
  [12] send_notification       → 15 min

Total estimated: ~4.5 hours (with buffer)
```

---

## Testing Checklist

- [ ] Each tool runs standalone with a hardcoded JSON input (no Step Functions needed)
- [ ] All tools return the `build_response_envelope` format
- [ ] `scan_logs` correctly reads all 4 time-window files and groups errors
- [ ] `query_metrics` computes baseline vs. peak and detects all 5 anomalous metrics
- [ ] `get_deployments` identifies `deploy-20260206-1400` as highest risk
- [ ] `correlate_deploy_to_incident` returns score > 0.9 for the DB pool change
- [ ] `invoke_bedrock` returns valid JSON (not free-text) in both plan and decide modes
- [ ] `generate_rca_report` produces a readable Markdown file
- [ ] `save_state` / `load_state` round-trip correctly in DynamoDB
