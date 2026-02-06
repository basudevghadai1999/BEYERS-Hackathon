import re
from typing import Dict, Optional


def extract_stack_traces(log_entry: Dict) -> Optional[Dict]:
    """
    Parses stack traces from log entries and extracts the top frame.
    """
    stack_trace = log_entry.get("stack_trace")
    if not stack_trace:
        return None

    # Regex for Java stack trace frames: (\w[\w.]*)\((\w+\.java):(\d+)\)
    # Example: com.bayer.checkout.db.ConnectionPool.acquire(ConnectionPool.java:142)
    pattern = r"([\w\.]+)\(([\w\.]+):(\d+)\)"
    matches = re.finditer(pattern, stack_trace)

    frames = []
    for match in matches:
        full_path = match.group(1)
        file_name = match.group(2)
        line_number = int(match.group(3))

        parts = full_path.split(".")
        method = parts[-1]
        class_name = parts[-2] if len(parts) > 1 else full_path

        frames.append(
            {
                "class": class_name,
                "method": method,
                "file": file_name,
                "line": line_number,
                "full_path": full_path,
            }
        )

    if not frames:
        return None

    return {
        "root_frame": frames[0],
        "call_chain": [f["full_path"] for f in frames[:5]],
        "depth": len(frames),
    }
