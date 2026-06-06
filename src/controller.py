import time
import httpx
import numpy as np
import sys
sys.path.insert(0, ".")
from scripts.prometheus_converter import prepare_timesfm_input, scale_to_pod_count
from datetime import datetime, timedelta

PROMETHEUS_URL = "http://localhost:9090"
TIMESFM_URL = "http://localhost:8001"
DEPLOYMENT_NAME = "autoscaler-plugin"
NAMESPACE = "default"
LOOP_INTERVAL = 60
MIN_PODS = 1
MAX_PODS = 2

def get_cpu_metrics(retries=3) -> np.ndarray:
    """Prometheus'tan CPU metriklerini ceker, basarisiz olursa tekrar dener."""
    end = datetime.now()
    start = end - timedelta(minutes=30)
    params = {
        "query": "avg(rate(container_cpu_usage_seconds_total{namespace='default', pod=~'autoscaler-plugin-.*'}[1m]))",
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": "15s"
    }
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params)
            data = response.json()
            results = data["data"]["result"]
            if not results:
                raise ValueError("Prometheus'tan veri alinamadi")
            values = [float(v[1]) for v in results[0]["values"]]
            return np.array(values, dtype=np.float32)
        except Exception as e:
            print(f"  Prometheus deneme {attempt+1}/{retries} basarisiz: {e}")
            if attempt < retries - 1:
                time.sleep(5)
    raise RuntimeError("Prometheus'a erisim saglanamadi")

def get_forecast(values: np.ndarray, retries=3) -> list:
    """TimesFM'den tahmin alir, basarisiz olursa tekrar dener."""
    prepared = prepare_timesfm_input(values, context_len=128)
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{TIMESFM_URL}/predict",
                    json={"values": prepared.tolist(), "horizon": 5}
                )
            return response.json()["forecast"]
        except Exception as e:
            print(f"  TimesFM deneme {attempt+1}/{retries} basarisiz: {e}")
            if attempt < retries - 1:
                time.sleep(5)
    raise RuntimeError("TimesFM'e erisim saglanamadi")

def scale_deployment(pod_count: int):
    """kubectl ile deployment'i olcekler."""
    import subprocess
    cmd = [
        "kubectl", "scale", "deployment", DEPLOYMENT_NAME,
        f"--replicas={pod_count}",
        f"--namespace={NAMESPACE}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Deployment {pod_count} replica'ya olceklendi")
    else:
        print(f"  Olcekleme hatasi: {result.stderr}")

def control_loop():
    """Ana kontrol dongusu - 60 saniyede bir calisir."""
    print("Controller baslatildi!")
    print(f"  Hedef: {DEPLOYMENT_NAME} ({NAMESPACE})")
    print(f"  Aralik: {LOOP_INTERVAL} saniye")
    print(f"  Pod araligi: {MIN_PODS} - {MAX_PODS}")
    print("-" * 50)

    while True:
        try:
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{now}] Kontrol dongusu basliyor...")

            print("  Prometheus'tan veri cekiliyor...")
            values = get_cpu_metrics()
            print(f"  {len(values)} veri noktasi alindi")

            print("  TimesFM tahmini yapiliyor...")
            forecast = get_forecast(values)
            print(f"  Tahmin: {[round(f, 4) for f in forecast]}")

            pod_counts = scale_to_pod_count(forecast, MIN_PODS, MAX_PODS)
            target_pods = pod_counts[0]
            print(f"  Hedef pod sayisi: {target_pods}")

            scale_deployment(target_pods)
            print(f"  Sonraki kontrol {LOOP_INTERVAL} saniye sonra...")

        except Exception as e:
            print(f"  KRITIK HATA: {e}")
            print(f"  {LOOP_INTERVAL} saniye sonra tekrar denenecek...")

        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    control_loop()
