import httpx
import numpy as np
import sys
sys.path.insert(0, ".")
from scripts.prometheus_converter import prepare_timesfm_input, scale_to_pod_count
from datetime import datetime, timedelta

with httpx.Client(timeout=120.0) as client:

    # 1. Prometheus'tan veri cek
    print("Adim 1: Prometheus'tan veri cekiliyor...")
    end = datetime.now()
    start = end - timedelta(minutes=30)

    params = {
        "query": "rate(container_cpu_usage_seconds_total{namespace='default'}[1m])",
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": "15s"
    }

    response = client.get("http://localhost:9090/api/v1/query_range", params=params)
    data = response.json()
    results = data["data"]["result"]
    values = [float(v[1]) for v in results[0]["values"]]
    print(f"  {len(values)} veri noktasi alindi")

    # 2. TimesFM formatina hazirla
    print("Adim 2: TimesFM formatina donusturuluyor...")
    prepared = prepare_timesfm_input(np.array(values, dtype=np.float32), context_len=128)
    print(f"  Girdi uzunlugu: {len(prepared)}")

    # 3. TimesFM ile tahmin yap
    print("Adim 3: TimesFM ile tahmin yapiliyor...")
    forecast_response = client.post(
        "http://localhost:8001/predict",
        json={"values": prepared.tolist(), "horizon": 5}
    )
    forecast = forecast_response.json()["forecast"]
    print(f"  Tahmin: {[round(f, 2) for f in forecast]}")

    # 4. Pod sayisina donustur
    print("Adim 4: Pod sayisina donusturuluyor...")
    pod_counts = scale_to_pod_count(forecast, min_pods=1, max_pods=10)
    print(f"  Oneri edilen pod sayilari (5 dk): {pod_counts}")
    print(f"  Simdi gereken pod sayisi: {pod_counts[0]}")
    print("\nPipeline tamamlandi!")
