import httpx
import numpy as np
import sys
sys.path.insert(0, ".")
from scripts.prometheus_converter import prepare_timesfm_input, scale_to_pod_count
from datetime import datetime, timedelta

end = datetime.now()
start = end - timedelta(minutes=10)

params = {
    "query": "rate(container_cpu_usage_seconds_total{namespace='default'}[1m])",
    "start": start.timestamp(),
    "end": end.timestamp(),
    "step": "15s"
}

response = httpx.get("http://localhost:9090/api/v1/query_range", params=params)
data = response.json()
print("Status:", data["status"])
results = data["data"]["result"]
print("Metrik sayisi:", len(results))
if results:
    values = [float(v[1]) for v in results[0]["values"]]
    print("Veri nokta sayisi:", len(values))
    print("Ilk 5 deger:", values[:5])
