import json
import os
import time
from datetime import datetime
from config import LOG_DIR

NODE_LOG_FILE = os.path.join(LOG_DIR, "node_execution.json")
GRAPH_LOG_FILE = os.path.join(LOG_DIR, "graph_execution.json")


def log_node_execution(session_id, node_name, input_data, output_data, execution_time, token_usage):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "node": node_name,
        "execution_time_seconds": round(execution_time, 4),
        "estimated_tokens": token_usage,
        "input_preview": str(input_data)[:300],
        "output_preview": str(output_data)[:300]
    }

    with open(NODE_LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def log_graph_summary(session_id, total_time):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "total_graph_execution_time_seconds": round(total_time, 4)
    }

    with open(GRAPH_LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
