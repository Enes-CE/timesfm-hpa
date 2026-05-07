import numpy as np
import pandas as pd
import httpx
import time
import json
import sys
sys.path.insert(0, ".")
from models.lightgbm_baseline import LightGBMForecaster
from scripts.prometheus_converter import scale_to_pod_count
from datetime import datetime

# Ayarlar
TIMESFM_URL = "http://localhost:8001"
MIN_PODS = 1
MAX_PODS = 5
SLA_THRESHOLD_MS = 1000  # 1 saniye

# ─── Trafik Üreticileri ───────────────────────────────────────────

def generate_periodic(n=200):
    """Dönemsel trafik: sinüs dalgası"""
    t = np.linspace(0, 4 * np.pi, n)
    return (50 + 30 * np.sin(t) + np.random.normal(0, 2, n)).astype(np.float32)

def generate_burst(n=200):
    """Burst trafik: ani yük artışı"""
    values = np.ones(n) * 20
    values[60:90] = 90
    values[130:150] = 85
    return (values + np.random.normal(0, 2, n)).astype(np.float32)

def generate_onoff(n=200):
    """On-Off trafik: açık/kapalı"""
    values = np.zeros(n)
    for i in range(n):
        values[i] = 80 if (i // 30) % 2 == 0 else 10
    return (values + np.random.normal(0, 2, n)).astype(np.float32)

# ─── Tahmin Stratejileri ─────────────────────────────────────────

def predict_timesfm(values: np.ndarray) -> list:
    """TimesFM ile tahmin"""
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{TIMESFM_URL}/predict",
            json={"values": values.tolist(), "horizon": 5}
        )
    return response.json()["forecast"]

def predict_lightgbm(values: np.ndarray, forecaster: LightGBMForecaster) -> list:
    """LightGBM ile tahmin"""
    return forecaster.predict(values)

def predict_reactive(values: np.ndarray) -> list:
    """Reaktif HPA: sadece mevcut değere bakır"""
    current = float(values[-1])
    return [current] * 5

# ─── Metrik Hesaplama ────────────────────────────────────────────

def simulate_response_time(pod_count: int, load: float) -> float:
    """
    Pod sayısı ve yüke göre yanıt süresi simüle eder.
    Gerçekçi bir model: yük/kapasite oranı arttıkça yanıt süresi artar.
    """
    capacity = pod_count * 20.0
    utilization = load / capacity if capacity > 0 else 1.0
    utilization = min(utilization, 2.0)
    
    if utilization < 0.5:
        base_ms = 100
    elif utilization < 0.8:
        base_ms = 200 + (utilization - 0.5) * 1000
    elif utilization < 1.0:
        base_ms = 500 + (utilization - 0.8) * 5000
    else:
        base_ms = 1500 + (utilization - 1.0) * 3000
    
    noise = np.random.normal(0, base_ms * 0.1)
    return max(50, base_ms + noise)

def run_experiment(traffic_name: str, traffic_values: np.ndarray, 
                   strategy_name: str, forecaster=None) -> dict:
    """Tek bir deney senaryosunu çalıştırır."""
    print(f"\n  [{traffic_name} x {strategy_name}] Deney başlıyor...")
    
    context_len = 50
    response_times = []
    pod_counts_used = []
    sla_violations = 0
    
    for i in range(context_len, len(traffic_values) - 5):
        context = traffic_values[i-context_len:i]
        current_load = float(traffic_values[i])
        
        # Tahmin yap
        try:
            if strategy_name == "TimesFM":
                forecast = predict_timesfm(context)
            elif strategy_name == "LightGBM":
                forecast = predict_lightgbm(context, forecaster)
            else:  # Reaktif
                forecast = predict_reactive(context)
        except Exception as e:
            forecast = [current_load] * 5
        
        # Pod sayısı hesapla
        pod_counts = scale_to_pod_count(forecast, MIN_PODS, MAX_PODS)
        target_pods = pod_counts[0]
        
        # Yanıt süresi simüle et
        rt = simulate_response_time(target_pods, current_load)
        response_times.append(rt)
        pod_counts_used.append(target_pods)
        
        if rt > SLA_THRESHOLD_MS:
            sla_violations += 1
    
    total = len(response_times)
    results = {
        "traffic": traffic_name,
        "strategy": strategy_name,
        "avg_response_ms": np.mean(response_times),
        "p95_response_ms": np.percentile(response_times, 95),
        "p99_response_ms": np.percentile(response_times, 99),
        "sla_violation_pct": (sla_violations / total) * 100,
        "avg_pods": np.mean(pod_counts_used),
        "total_samples": total
    }
    
    print(f"    Ort. yanıt: {results['avg_response_ms']:.1f}ms")
    print(f"    SLA ihlali: {results['sla_violation_pct']:.1f}%")
    print(f"    Ort. pod:   {results['avg_pods']:.2f}")
    
    return results

# ─── Ana Deney Döngüsü ───────────────────────────────────────────

def run_all_experiments():
    print("=" * 60)
    print("KARSILASTIRMALI DENEY BASLIYOR")
    print("3 Trafik x 3 Strateji = 9 Senaryo")
    print("=" * 60)
    
    # Trafik verilerini üret
    traffic_patterns = {
        "Periyodik": generate_periodic(200),
        "Burst":     generate_burst(200),
        "OnOff":     generate_onoff(200)
    }
    
    # LightGBM modellerini eğit
    print("\nLightGBM modelleri egitiliyor...")
    lgbm_models = {}
    for name, values in traffic_patterns.items():
        f = LightGBMForecaster(horizon=5)
        f.train(values[:150])
        lgbm_models[name] = f
    print("LightGBM egitimi tamamlandi!")
    
    # 9 deneyi çalıştır
    strategies = ["TimesFM", "LightGBM", "Reaktif"]
    all_results = []
    
    for traffic_name, traffic_values in traffic_patterns.items():
        for strategy in strategies:
            forecaster = lgbm_models[traffic_name] if strategy == "LightGBM" else None
            result = run_experiment(traffic_name, traffic_values, strategy, forecaster)
            all_results.append(result)
    
    # Sonuçları kaydet
    df = pd.DataFrame(all_results)
    df.to_csv("experiments/results.csv", index=False)
    
    print("\n" + "=" * 60)
    print("SONUCLAR")
    print("=" * 60)
    print(df[["traffic", "strategy", "avg_response_ms", "sla_violation_pct", "avg_pods"]].to_string(index=False))
    print("\nSonuclar experiments/results.csv dosyasina kaydedildi!")
    
    return df

if __name__ == "__main__":
    run_all_experiments()
