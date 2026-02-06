# Implementation Plan — Autonomous Incident Commander (AIC)

> Bayer AI Hackathon 2026 | 8-hour build | 2-3 person team | Starting from scratch

---

## Confirmed Decisions (from interview)

| Area | Decision |
|------|----------|
| Agent Framework | Google ADK with **A2A protocol** |
| A2A Transport | **InProcessTransport** (in-memory, no HTTP) |
| Agent Discovery | **Static agent card registration** |
| Task Dispatch | **Async with polling** |
| Packaging | **ECR container image** (`public.ecr.aws/lambda/python:3.12`) |
| Lambda Config | **15 min timeout / 3008 MB** |
| Commander Model | **Opus 4.5** (`anthropic.claude-opus-4-5-20251101`) via ADK LLM wrapper |
| Sub-agent Model | **Sonnet 4.5** (`anthropic.claude-sonnet-4-5-20250929`) via ADK LLM wrapper |
| Data Pipeline | **Full CloudWatch** — seeder Lambda hydrates CW Logs + Metrics from mock S3 data |
| Metric Seeding | **Backfill historical** + **live push breach points** to trigger alarm |
| Logs Agent Query | **CloudWatch Logs Insights** (StartQuery / GetQueryResults) |
| Metrics Agent Query | **CloudWatch GetMetricData** API |
| Deploy Agent Query | **S3** (deploy history doesn't live in CloudWatch) |
| State Management | **Hybrid** — in-memory for agent comms, DynamoDB for findings + decisions (eval datasets) |
| DynamoDB Granularity | **Findings + decisions only** (not every A2A message) |
| Failure Handling | **Retry once**, then **escalate to human** via SNS |
| Confidence Score | **Hybrid: deterministic formula + Opus LLM adjust** (±0.15 max) |
| ACT Phase | **Mock/log only** — no real rollback |
| Demo Outputs | **RCA Markdown in S3** + **SNS alert notification** |
| LLM Integration | **ADK built-in LLM wrapper** (model='bedrock/...') |

---

## Project Structure (revised for ADK + A2A + ECR)

```
autonomous-incident-commander/
├── arch.md                          # (exists)
├── tools.md                         # (exists)
├── CLOUDWATCH_TRIGGER_GUIDE.md      # (exists)
├── mock_data/                       # (exists — 11 JSON files)
│
├── Dockerfile                       # ECR container build
├── requirements.txt                 # google-adk, boto3, etc.
│
├── app/
│   ├── __init__.py
│   ├── handler.py                   # Lambda entry point
│   ├── bootstrap.py                 # ADK app init + A2A wiring
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── commander.py             # Commander ADK agent (Opus 4.5)
│   │   ├── logs_agent.py            # Logs ADK agent (Sonnet 4.5)
│   │   ├── metrics_agent.py         # Metrics ADK agent (Sonnet 4.5)
│   │   └── deploy_agent.py          # Deploy Intel ADK agent (Sonnet 4.5)
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── parse_alarm.py           # parse_alarm_event
│   │   ├── cloudwatch_logs.py       # query_logs_insights (Logs Insights API)
│   │   ├── cloudwatch_metrics.py    # get_metric_data (GetMetricData API)
│   │   ├── s3_deployments.py        # get_deployments (S3 read)
│   │   ├── stack_parser.py          # extract_stack_traces
│   │   ├── anomaly_detector.py      # detect_anomalies (z-score)
│   │   ├── deploy_correlator.py     # correlate_deploy_to_incident
│   │   ├── state_store.py           # save_state / load_state (DynamoDB)
│   │   ├── report_generator.py      # generate_rca_report (S3 upload)
│   │   ├── notifier.py              # send_notification (SNS)
│   │   └── envelope.py              # build_response_envelope
│   │
│   └── prompts/
│       ├── commander_plan.txt        # PLAN phase system prompt
│       ├── commander_decide.txt      # DECIDE phase system prompt
│       ├── logs_agent.txt            # Logs agent instructions
│       ├── metrics_agent.txt         # Metrics agent instructions
│       └── deploy_agent.txt          # Deploy agent instructions
│
├── seeder/
│   ├── handler.py                    # Seeder Lambda entry point
│   ├── seed_logs.py                  # Push mock logs → CW Logs
│   ├── seed_metrics.py               # Push mock metrics → CW Metrics
│   └── requirements.txt
│
├── infra/
│   ├── app.py                        # CDK app entry
│   ├── cdk.json
│   └── stacks/
│       ├── ecr_stack.py              # ECR repo
│       ├── data_stack.py             # DynamoDB + S3 buckets
│       ├── compute_stack.py          # Commander Lambda + Seeder Lambda
│       ├── events_stack.py           # CloudWatch Alarm + EventBridge rule
│       └── notification_stack.py     # SNS topic
│
└── tests/
    ├── test_parse_alarm.py
    ├── test_tools.py
    └── test_local_invoke.py          # Direct handler call with mock event
```

---

## Step-by-Step Implementation

### Step 1 — Scaffold + Dockerfile + Requirements

**Files:** `Dockerfile`, `requirements.txt`

**Dockerfile:**
```dockerfile
FROM public.ecr.aws/lambda/python:3.12
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY mock_data/ ${LAMBDA_TASK_ROOT}/mock_data/
CMD ["app.handler.lambda_handler"]
```

**requirements.txt:**
```
google-adk>=1.0.0
boto3>=1.35.0
```

---

### Step 2 — Shared Tools (build first — everything depends on these)

**Files to create:**
- `app/tools/parse_alarm.py` — extract incident context from EventBridge event (see tools.md Tool 1)
- `app/tools/state_store.py` — `save_state()` and `load_state()` using DynamoDB (tools.md Tools 3-4)
- `app/tools/envelope.py` — `build_response_envelope()` standard wrapper (tools.md Tool 13)

All three are pure Python functions decorated with `@tool` for ADK.

**DynamoDB write points** (exactly where `save_state` is called):
1. `handler.py` after alarm parse → writes `META#0`
2. `commander.py` after PLAN → writes `PLAN#<ts>`
3. Each sub-agent on completion → writes `FINDING#<agent>#<ts>`
4. `commander.py` after DECIDE → writes `DECISION#<ts>`
5. `commander.py` after ACT → writes `ACTION#<ts>`
6. `report_generator.py` after S3 upload → writes `REPORT#<ts>`

---

### Step 3 — CloudWatch Query Tools (replacing S3-based tools)

**File: `app/tools/cloudwatch_logs.py`**
- Tool name: `query_logs_insights`
- Uses `boto3.client("logs")` → `start_query()` + poll `get_query_results()`
- Logs Insights query template:
  ```
  fields @timestamp, @message, level, error_code, stack_trace, metadata.pool_active, metadata.pool_max
  | filter level in ["ERROR","FATAL","WARN"]
  | filter @timestamp >= '{start}' and @timestamp <= '{end}'
  | sort @timestamp asc
  | limit 50
  ```
- Log group: `/bayer/{service}` (e.g., `/bayer/checkout-service`)
- Polls with 1s interval, max 30 retries (Logs Insights is async)

**File: `app/tools/cloudwatch_metrics.py`**
- Tool name: `get_metric_data`
- Uses `boto3.client("cloudwatch")` → `get_metric_data()`
- Fetches: `p99_latency_ms`, `cpu_utilization_percent`, `memory_utilization_percent`, `db_connection_pool_active`, `db_connection_wait_queue`, `error_rate_percent`
- Computes: baseline avg (pre-anomaly), peak value, change_factor, trend

**File: `app/tools/s3_deployments.py`**
- Tool name: `get_deployments` (unchanged — reads S3 JSON)
- Deploy history stays in S3 since it doesn't naturally belong in CloudWatch

---

### Step 4 — ADK Agent Definitions + A2A Wiring

**File: `app/bootstrap.py`** — ADK application initialization
- Creates 4 ADK Agent instances:
  - `commander_agent` with model=`bedrock/anthropic.claude-opus-4-5-20251101`
  - `logs_agent` with model=`bedrock/anthropic.claude-sonnet-4-5-20250929`
  - `metrics_agent` with model=`bedrock/anthropic.claude-sonnet-4-5-20250929`
  - `deploy_agent` with model=`bedrock/anthropic.claude-sonnet-4-5-20250929`
- Registers static agent cards (name, description, tools list)
- Wires `InProcessTransport` — all agents share the same transport bus
- Commander holds references to sub-agents by name

**File: `app/agents/commander.py`**
- Defines Commander Agent with tools: `parse_alarm_event`, `save_state`, `load_state`
- PLAN phase: Opus generates investigation plan with hypothesis + time window + agent assignments
- INVESTIGATE phase: dispatches A2A tasks to 3 sub-agents via `InProcessTransport`, polls for completion (async)
- Retry logic: if a sub-agent fails, retry once, then mark as failed
- DECIDE phase: receives all findings, runs hybrid confidence scoring:
  - **Base score** = `(logs_confidence * 0.35) + (metrics_confidence * 0.30) + (deploy_confidence * 0.35)`
  - **Evidence boost** = +0.05 if timestamp overlap between log errors and metric anomalies, +0.05 if deploy config matches error type
  - **LLM adjust** = Opus can modify by ±0.15 with explicit reasoning
  - If any sub-agent failed: penalty of -0.20
- ACT phase: if confidence >= 0.8 → log "rollback recommended" (mock). Otherwise → SNS escalation.

**File: `app/agents/logs_agent.py`**
- Sonnet 4.5 agent with tools: `query_logs_insights`, `extract_stack_traces`, `build_response_envelope`
- Instructions: query CW Logs for errors in the incident time window, summarize error codes, extract stack traces

**File: `app/agents/metrics_agent.py`**
- Sonnet 4.5 agent with tools: `get_metric_data`, `detect_anomalies`, `build_response_envelope`
- Instructions: fetch all metrics for the service, identify anomaly start time, compute degradation factors

**File: `app/agents/deploy_agent.py`**
- Sonnet 4.5 agent with tools: `get_deployments`, `correlate_deploy_to_incident`, `build_response_envelope`
- Instructions: find deployments in the time window, score correlation, identify highest-risk deploy

---

### Step 5 — Lambda Handler (entry point)

**File: `app/handler.py`**
```
1. Receive event (EventBridge alarm or direct invoke)
2. Normalize: extract alarm detail from event["detail"] or event itself
3. Call parse_alarm_event → structured incident context
4. save_state(META#0) → DynamoDB
5. Initialize ADK application (bootstrap.py)
6. Hand off to Commander Agent with incident context
7. Commander runs PLAN → INVESTIGATE → DECIDE → ACT → REPORT
8. Return { statusCode, body: { incident_id, report_url, decision, confidence } }
```

---

### Step 6 — CloudWatch Seeder Lambda

**File: `seeder/handler.py`**
- Separate Lambda (plain Python 3.12 zip, not container)
- Reads mock JSON from S3 bucket
- `seed_logs.py`:
  - Creates log groups: `/bayer/checkout-service`, `/bayer/payment-service`, `/bayer/inventory-service`
  - Creates log stream per instance_id
  - Pushes each log entry via `put_log_events` with correct timestamps
  - CloudWatch requires events in chronological order per stream + sequence tokens
- `seed_metrics.py`:
  - Pushes all metric datapoints via `put_metric_data` (max 1000 per call, batch by 20)
  - Namespace: `Bayer/CheckoutService`, `Bayer/PaymentService`, `Bayer/InventoryService`
  - Dimensions: `ServiceName`, `Environment=production`
  - Backfills all historical points, then pushes the 2 breach points (2100, 2300) last

---

### Step 7 — Report Generator + SNS

**File: `app/tools/report_generator.py`**
- Builds RCA Markdown from template (see tools.md Tool 12 for full template)
- Uploads to `s3://{REPORTS_BUCKET}/INC-{id}/rca.md` with `ContentType=text/markdown`
- Returns S3 URI + presigned URL

**File: `app/tools/notifier.py`**
- Publishes to SNS with `MessageStructure=json`
- Subject: `[AIC] CRITICAL — INC-{id} — Rollback Recommended`
- Body includes incident summary + report link

---

### Step 8 — CDK Infrastructure

**Stacks to create:**

1. **`ecr_stack.py`** — ECR repository `aic-commander`
2. **`data_stack.py`** — DynamoDB table `AIC-IncidentState` (PK/SK + GSI on status), S3 buckets for mock data + reports
3. **`compute_stack.py`** — Commander Lambda (container from ECR, 15min/3008MB, env vars, IAM for CW Logs/Metrics read + DynamoDB + S3 + Bedrock + SNS), Seeder Lambda (Python zip, IAM for CW Logs/Metrics write + S3 read)
4. **`events_stack.py`** — CloudWatch Alarm on `Bayer/CheckoutService` / `p99_latency_ms` > 2000 for 2 periods, EventBridge rule targeting Commander Lambda, Lambda permission for EventBridge
5. **`notification_stack.py`** — SNS topic `aic-incident-alerts`

---

### Step 9 — Prompt Engineering

**File: `app/prompts/commander_plan.txt`**
```
You are an expert SRE incident commander. Given a CloudWatch alarm event, generate
an investigation plan as JSON. Include:
- hypothesis (string)
- steps (array of {agent, task})
- priority_service (string)
- time_window ({start, end} ISO timestamps — extend 30 min before alarm)
Always assign all 3 agents: logs_agent, metrics_agent, deploy_agent.
```

**File: `app/prompts/commander_decide.txt`**
```
You are an expert SRE incident commander. You receive findings from 3 investigation
agents. Correlate the evidence and return JSON:
- root_cause (string — 1-2 sentences)
- evidence_chain (array of strings — causal links)
- base_confidence (float — from the formula provided)
- adjusted_confidence (float — your adjustment, max ±0.15 from base)
- adjustment_reasoning (string — why you adjusted)
- recommended_action ("rollback" if adjusted_confidence >= 0.8, else "escalate")
- rollback_target ({service, version} if rollback)
```

---

## 8-Hour Sprint Plan (2-3 people)

| Time | Sprint | Person A | Person B | Person C (if present) |
|------|--------|----------|----------|-----------------------|
| **10:00–11:30** | Sprint 0 | CDK stacks + infra deploy | Dockerfile + requirements + scaffold | Shared tools (parse_alarm, state_store, envelope) |
| **11:30–13:00** | Sprint 1 | CloudWatch seeder Lambda (seed_logs + seed_metrics) | Commander agent + A2A bootstrap + handler.py | CloudWatch query tools (logs insights + get_metric_data) |
| **13:00–14:00** | *Lunch* | | | |
| **14:00–16:00** | Sprint 2 | Logs Agent + Metrics Agent (ADK definitions + tools) | Deploy Agent + correlator + stack_parser | Commander DECIDE logic + confidence scoring |
| **16:00–18:00** | Sprint 3 | Report generator + SNS notifier | ECR build + deploy + EventBridge wiring | End-to-end test: seed → trigger → investigate → report |

If 2 people: Person A takes infra + seeder + sub-agents, Person B takes container + Commander + demo.

---

## Verification — End-to-End Test

1. `cdk deploy` — all stacks
2. `aws s3 sync mock_data/ s3://aic-mock-data-<acct>/` — upload mock data
3. Invoke seeder Lambda — hydrates CloudWatch Logs + Metrics
4. Verify in CloudWatch console: log groups exist, metrics visible in Metrics Explorer
5. Push breach metrics (2100, 2300) → alarm transitions to ALARM
6. Check CloudWatch Logs for Commander Lambda — see full DETECT→PLAN→INVESTIGATE→DECIDE→ACT→REPORT chain
7. Check S3 reports bucket — RCA markdown exists
8. Check SNS — notification delivered
9. Check DynamoDB — META, PLAN, 3x FINDING, DECISION, ACTION, REPORT entries exist
10. **Fallback test:** Direct invoke via `boto3 lambda.invoke()` with `mock_data/cloudwatch_alarm.json` mock event
