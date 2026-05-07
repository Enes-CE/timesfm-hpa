from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import numpy as np
import timesfm

app = FastAPI(title="Predictive Autoscaler API")

# Prometheus metrics
PREDICTION_COUNTER = Counter("predictions_total", "Total number of predictions made")
PREDICTION_LATENCY = Histogram("prediction_latency_seconds", "Prediction latency")

# Global model variable
model = None
forecast_config = None

@app.on_event("startup")
async def load_model():
    global model, forecast_config
    print("Loading TimesFM model...")
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        "google/timesfm-2.5-200m-pytorch"
    )
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
