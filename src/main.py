from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import numpy as np
import os
import timesfm

app = FastAPI(title="Predictive Autoscaler API")

# Prometheus metrics
PREDICTION_COUNTER = Counter("predictions_total", "Total number of predictions made")
PREDICTION_LATENCY = Histogram("prediction_latency_seconds", "Prediction latency")

# Model yapilandirmasi
# MODEL_PATH: modelin saklanacagi/yuklenecegi yerel klasor (PersistentVolume icin)
# HF_MODEL_ID: yerel model yoksa Hugging Face'ten indirilecek model
MODEL_PATH = os.environ.get("MODEL_PATH", "/app/models/timesfm")
HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "google/timesfm-2.5-200m-pytorch")

# Global model variable
model = None
forecast_config = None

def _has_local_model(path: str) -> bool:
    # Klasorde gercek agirlik dosyasi (safetensors/bin) var mi kontrol et
    if not os.path.isdir(path):
        return False
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith((".safetensors", ".bin", ".ckpt")):
                return True
    return False

@app.on_event("startup")
async def load_model():
    global model, forecast_config

    if _has_local_model(MODEL_PATH):
        # Yerel model var -> internet gerekmez, dogrudan yukle
        print(f"Yerel model bulundu, yukleniyor: {MODEL_PATH}")
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(MODEL_PATH)
    else:
        # Yerel model yok -> Hugging Face'ten indir, MODEL_PATH'e kaydet
        print(f"Yerel model yok. Hugging Face'ten indiriliyor: {HF_MODEL_ID}")
        from huggingface_hub import snapshot_download
        os.makedirs(MODEL_PATH, exist_ok=True)
        snapshot_download(repo_id=HF_MODEL_ID, local_dir=MODEL_PATH)
        print(f"Indirme tamam. Yerel model yukleniyor: {MODEL_PATH}")
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(MODEL_PATH)

    print("Compiling TimesFM model...")
    forecast_config = timesfm.ForecastConfig(
        max_context=128,
        max_horizon=10,
        normalize_inputs=True,
    )
    model.compile(forecast_config)
    print("TimesFM model loaded and compiled successfully!")

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}

@app.post("/predict")
def predict(data: dict):
    values = data.get("values", [])
    horizon = data.get("horizon", 5)
    with PREDICTION_LATENCY.time():
        input_array = np.array(values, dtype=np.float32)
        forecast, _ = model.forecast(
            horizon=horizon,
            inputs=[input_array],
        )
        PREDICTION_COUNTER.inc()
        return {"forecast": forecast[0].tolist()}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
