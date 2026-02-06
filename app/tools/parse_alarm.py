"""parse_alarm_event — extracts structured incident context from EventBridge alarm event."""

import json
from datetime import datetime, timezone


def parse_alarm_event(event: dict) -> dict:
    """Extracts structured incident context from a CloudWatch Alarm EventBridge event.

    Args:
        event: Raw EventBridge event dict.

    Returns:
        Structured incident context dict.
    """
    detail = event.get("detail", event)

    alarm_name = detail.get("alarmName", "")
    state = detail.get("state", {})
    prev_state = detail.get("previousState", {})
    config = detail.get("configuration", {})

    service = _extract_service_from_alarm(alarm_name)

    metric_name = ""
    namespace = ""
    metrics_config = config.get("metrics", [])
    if metrics_config:
        metric_stat = metrics_config[0].get("metricStat", {}).get("metric", {})
        metric_name = metric_stat.get("name", "")
        namespace = metric_stat.get("namespace", "")

    # reasonData is a JSON string inside JSON
    reason_data = {}
    raw_reason_data = state.get("reasonData", "")
    if raw_reason_data:
        try:
            reason_data = json.loads(raw_reason_data)
        except (json.JSONDecodeError, TypeError):
            pass

    threshold = reason_data.get("threshold", 0.0)
    current_values = reason_data.get("recentDatapoints", [])

    detected_at = state.get("timestamp", event.get("time", ""))
    if detected_at and not detected_at.endswith("Z") and "+" not in detected_at:
        detected_at += "Z"

    try:
        dt = datetime.fromisoformat(
            detected_at.replace("Z", "+00:00").replace("+0000", "+00:00")
        )
    except (ValueError, AttributeError):
        dt = datetime.now(timezone.utc)
    incident_id = f"INC-{dt.strftime('%Y%m%d-%H%M%S')}"

    return {
        "incident_id": incident_id,
        "service": service,
        "alarm_name": alarm_name,
        "metric_name": metric_name,
        "namespace": namespace,
        "threshold": threshold,
        "current_values": current_values,
        "alarm_state": state.get("value", "ALARM"),
        "previous_state": prev_state.get("value", "OK"),
        "detected_at": detected_at,
        "region": event.get("region", "us-east-1"),
        "alarm_reason": state.get("reason", ""),
        "account": event.get("account", ""),
    }


def _extract_service_from_alarm(alarm_name: str) -> str:
    known_services = [
        "checkout-service",
        "payment-service",
        "inventory-service",
    ]
    for svc in known_services:
        if alarm_name.startswith(svc):
            return svc
    parts = alarm_name.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return alarm_name
