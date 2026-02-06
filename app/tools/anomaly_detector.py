import statistics
from typing import List, Dict

def detect_anomalies(datapoints: List[Dict], method: str = "zscore", threshold: float = 2.0) -> Dict:
    """
    Flags datapoints as anomalies using z-score or static threshold.
    """
    if not datapoints:
        return {"anomalies": [], "baseline_mean": 0, "baseline_stddev": 0}
    
    values = [d["value"] for d in datapoints]
    
    if method == "zscore":
        if len(values) < 2:
            return {"anomalies": [], "baseline_mean": values[0], "baseline_stddev": 0}
        
        mean = statistics.mean(values)
        stddev = statistics.stdev(values)
        
        anomalies = []
        non_anomalous_values = []
        for d in datapoints:
            zscore = (d["value"] - mean) / stddev if stddev > 0 else 0
            if abs(zscore) > threshold:
                anomalies.append({**d, "zscore": zscore})
            else:
                non_anomalous_values.append(d["value"])
                
        baseline_mean = statistics.mean(non_anomalous_values) if non_anomalous_values else mean
        
        return {
            "anomalies": anomalies,
            "baseline_mean": baseline_mean,
            "baseline_stddev": stddev
        }
    else:
        # static threshold
        anomalies = [d for d in datapoints if d["value"] > threshold]
        return {"anomalies": anomalies}
