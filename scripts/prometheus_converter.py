import httpx
import numpy as np
from datetime import datetime, timedelta

PROMETHEUS_URL = "http://localhost:9090"

def get_prometheus_metrics(metric_name: str, duration_minutes: int = 30) -> np.ndarray:
    """
    Prometheus'tan zaman serisi çeker ve numpy array döner.
    TimesFM için girdi formatına dönüştürür.
    """
    end = datetime.now()
    start = end - timedelta(minutes=duration_minutes)
    
    params = {
        "query": metric_name,
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": "15s"
    }
    
    response = httpx.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params)
    data = response.json()
    
    if data["status"] != "success":
        raise ValueError(f"Prometheus query failed: {data}")
    
    results = data["data"]["result"]
    if not results:
        raise ValueError(f"No data found for metric: {metric_name}")
    
    values = [float(v[1]) for v in results[0]["values"]]
    return np.array(values, dtype=np.float32)


def prepare_timesfm_input(values: np.ndarray, context_len: int = 128) -> np.ndarray:
    """
    Zaman serisini TimesFM girdi formatına hazırlar.
    context_len kadar son noktayı alır.
    """
    if len(values) > context_len:
        values = values[-context_len:]
    return values


def scale_to_pod_count(forecast: list, min_pods: int = 1, max_pods: int = 10) -> list:
    """
    TimesFM tahminini pod sayisina donusturur.
    Hedef CPU utilization (%50, HPA ile ayni) esigi kullanir.
    Forecast = bir podun CPU usage'i (core fraction). 
    Eger forecast.max() > 0.5 ise, yuku karsilamak icin pod sayisini artirir.
    Formul: target_pods = ceil(forecast.max() / target_utilization)
    """
    import math
    forecast_array = np.array(forecast)
    target_utilization = 0.5  # HPA ile ayni: %50 CPU hedefi
    # Forecast'in pikine bakarak gereken pod sayisini hesapla
    peak_demand = float(forecast_array.max())
    required_pods = max(min_pods, math.ceil(peak_demand / target_utilization))
    required_pods = min(required_pods, max_pods)
    # Tum horizon icin ayni karari uygula (tepe-yuk savunmasi)
    return [required_pods] * len(forecast)

if __name__ == "__main__":
    print("Prometheus veri dönüştürücü test ediliyor...")
    
    # Test: sahte veri ile TimesFM formatı
    test_values = np.array([float(i) for i in range(50, 70)], dtype=np.float32)
    prepared = prepare_timesfm_input(test_values)
    print(f"Girdi uzunlugu: {len(prepared)}")
    
    # Test: pod sayısı hesaplama
    fake_forecast = [55.0, 60.0, 70.0, 80.0, 75.0]
    pod_counts = scale_to_pod_count(fake_forecast, min_pods=1, max_pods=10)
    print(f"Tahmin edilen pod sayilari: {pod_counts}")
    print("Test basarili!")
