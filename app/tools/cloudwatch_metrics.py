import boto3
import datetime
from typing import List, Dict


def get_metric_data(
    service: str, metric_names: List[str], time_window: Dict[str, str]
) -> Dict:
    """
    Fetches metric data from CloudWatch for a given service and time window.
    """
    cw = boto3.client("cloudwatch")

    start_time = datetime.datetime.fromisoformat(
        time_window["start"].replace("Z", "+00:00")
    )
    end_time = datetime.datetime.fromisoformat(
        time_window["end"].replace("Z", "+00:00")
    )

    # Match plan.md: Bayer/CheckoutService, Bayer/PaymentService
    namespace_service = "".join(word.capitalize() for word in service.split("-"))
    namespace = f"Bayer/{namespace_service}"

    queries = []
    for i, m in enumerate(metric_names):
        queries.append(
            {
                "Id": f"m{i}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": namespace,
                        "MetricName": m,
                        "Dimensions": [
                            {"Name": "ServiceName", "Value": service},
                            {"Name": "Environment", "Value": "production"},
                        ],
                    },
                    "Period": 60,
                    "Stat": "Average" if "latency" not in m else "p99",
                },
                "ReturnData": True,
            }
        )

    response = cw.get_metric_data(
        MetricDataQueries=queries, StartTime=start_time, EndTime=end_time
    )

    results = {}
    for res in response["MetricDataResults"]:
        m_idx = int(res["Id"][1:])
        m_name = metric_names[m_idx]
        results[m_name] = [
            {"timestamp": t.isoformat(), "value": v}
            for t, v in zip(res["Timestamps"], res["Values"])
        ]

    return results
