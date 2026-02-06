import datetime
from typing import Dict, List

def correlate_deploy_to_incident(deployments: List[Dict], anomaly_start: str, error_keywords: List[str] = None) -> Dict:
    """
    Scores deployments based on timing and message relevance.
    """
    if not deployments:
        return {"highest_risk_deploy": None, "correlations": []}
        
    incident_time = datetime.datetime.fromisoformat(anomaly_start.replace("Z", "+00:00"))
    correlations = []
    
    # Common risky keywords defined in plan.md
    risk_keywords = ["config", "pool", "db", "timeout", "connection", "limit", "scaling"]
    if error_keywords:
        risk_keywords.extend([k.lower() for k in error_keywords])

    for d in deployments:
        deploy_time = datetime.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
        
        # 1. Proximity Scoring (Plan.md: 0-0.3)
        time_diff = (incident_time - deploy_time).total_seconds() / 60
        proximity_score = 0.0
        if 0 <= time_diff <= 15:
            proximity_score = 0.3
        elif 0 <= time_diff <= 30:
            proximity_score = 0.2
        elif 0 <= time_diff <= 60:
            proximity_score = 0.1
            
        # 2. Relevance Scoring (Plan.md: 0-0.4)
        relevance_score = 0.0
        matched_keywords = [k for k in risk_keywords if k in d["message"].lower()]
        if matched_keywords:
            relevance_score = 0.4
            
        # 3. Baseline Score (Is it a config change? - Simplified)
        base_score = 0.2 if any(k in d["message"].lower() for k in ["config", "feat", "fix"]) else 0.1
        
        total_score = min(proximity_score + relevance_score + base_score, 1.0)
        
        correlations.append({
            **d,
            "correlation_score": round(total_score, 2),
            "minutes_before_incident": round(time_diff, 1),
            "matched_keywords": matched_keywords
        })
        
    # Sort by score descending
    correlations.sort(key=lambda x: x["correlation_score"], reverse=True)
    
    return {
        "highest_risk_deploy": correlations[0] if correlations else None,
        "correlations": correlations
    }
