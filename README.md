# TimesFM-HPA

**A Zero-Shot Foundation Model Based Predictive Autoscaler Plugin for Kubernetes**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.28+-326CE5.svg?logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![TimesFM](https://img.shields.io/badge/model-TimesFM--2.5--200M-orange.svg)](https://github.com/google-research/timesfm)
[![Docker Image](https://img.shields.io/docker/v/eenesulusoy/timesfm-hpa?label=docker&logo=docker)](https://hub.docker.com/r/eenesulusoy/timesfm-hpa)
[![Release](https://img.shields.io/github/v/release/Enes-CE/timesfm-hpa)](https://github.com/Enes-CE/timesfm-hpa/releases)
[![Status: Research Preview](https://img.shields.io/badge/status-research_preview-yellow.svg)]()

TimesFM-HPA is a Kubernetes predictive autoscaler that uses Google's TimesFM time-series foundation model to forecast workload patterns and proactively scale pods *before* demand spikes occur. Unlike traditional ML-based autoscalers, TimesFM-HPA requires **no per-workload training data** and operates in zero-shot mode out of the box.

## Key Features

- **Zero-shot deployment** — uses pretrained TimesFM-2.5-200M, no training required
- **Drop-in plugin** — works alongside any existing Kubernetes Deployment
- **Pre-built container image** — available on Docker Hub, one-command pull
- **Production-grade primitives** — startupProbe, readinessProbe, Prometheus integration, validated Helm chart (tested on minikube)
- **Open standard** — exposes a `/predict` HTTP endpoint, model-agnostic backend

## Experimental Results

Evaluated against the standard Kubernetes Horizontal Pod Autoscaler (HPA) on three canonical workload patterns. 10 independent runs per condition:

| Workload | p95 Latency Reduction | SLA Violation Rate | Statistical Significance |
|----------|----------------------|--------------------|--------------------------|
| Burst    | **50%**              | 40% → 30%          | p = 0.078                |
| Periodic | **68%**              | **80% → 0%**       | **p = 0.002**            |
| On-Off   | **61%**              | **50% → 0%**       | **p < 0.001**            |

Sustained throughput increased by 49–151%. Full results, statistics, and figures: [experiments/real_results/](experiments/real_results/).

## Architecture

The controller polls Prometheus every 60 seconds, requests a 5-step forecast from the TimesFM inference service, and proactively scales the target Deployment using `kubectl scale`.
Locust Client ──▶ Service ──▶ Pod 1..N (TimesFM)
│
▼
K8s API ◀── TimesFM Controller ◀── Prometheus
scale         forecast            metrics

## Quick Start

### Prerequisites

- Kubernetes cluster (tested on minikube 1.38+ with 5 GB memory)
- Prometheus + Grafana stack (kube-prometheus-stack)
- Helm 3+
- Python 3.12+ (for the controller)

### Install via Helm (Recommended)

```bash
git clone https://github.com/Enes-CE/timesfm-hpa.git
cd timesfm-hpa

helm install timesfm-hpa charts/timesfm-hpa \
  --set image.repository=eenesulusoy/timesfm-hpa \
  --set image.tag=v0.1.0 \
  --set controller.minReplicas=1 \
  --set controller.maxReplicas=10
```

The pre-built image is pulled automatically from Docker Hub. The TimesFM-2.5-200M model (~880 MB) is downloaded from Hugging Face Hub on first pod startup.

If using minikube, you may want to pre-load the image to avoid pull delays:

```bash
minikube image load eenesulusoy/timesfm-hpa:v0.1.0
```

### Manual Installation (Alternative)

If you prefer raw Kubernetes manifests:

```bash
docker pull eenesulusoy/timesfm-hpa:v0.1.0
kubectl apply -f k8s/deployment.yaml
kubectl wait --for=condition=Ready pod -l app=autoscaler-plugin --timeout=180s
```

To build from source instead of using the pre-built image:

```bash
docker build -t eenesulusoy/timesfm-hpa:v0.1.0 .
```

### Run the Predictive Controller

The controller runs as a separate process (outside the cluster, in this preview).

```bash
# Port-forward Prometheus and the inference service
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 &
kubectl port-forward svc/autoscaler-plugin-svc 8001:8001 &

# Install dependencies and run
pip install -r requirements.txt
python src/controller.py
```

The controller will:
1. Poll Prometheus every 60 seconds for the last 30 minutes of CPU history
2. Send the series to the TimesFM `/predict` endpoint for a 5-step forecast
3. Compute target replicas: `r_target = clamp(⌈û_peak / 0.5⌉, 1, r_max)`
4. Call `kubectl scale` to adjust the Deployment

### Compare Against Reactive HPA

To switch to reactive mode for baseline comparison:

```bash
# Stop the controller, then apply HPA
kubectl apply -f k8s/hpa.yaml
```

### Uninstall

```bash
helm uninstall timesfm-hpa
```

## Configuration

All parameters are configurable via Helm `--set` flags or a custom `values.yaml`. See [charts/timesfm-hpa/README.md](charts/timesfm-hpa/README.md) for the full reference. Key parameters:

| Parameter                        | Description                          | Default      |
|----------------------------------|--------------------------------------|--------------|
| `image.repository`               | Container image                      | `eenesulusoy/timesfm-hpa` |
| `image.tag`                      | Image version                        | `v0.1.0`     |
| `controller.minReplicas`         | Minimum replica count                | `1`          |
| `controller.maxReplicas`         | Maximum replica count                | `2`          |
| `controller.loopIntervalSeconds` | Control loop interval                | `60`         |
| `controller.targetUtilization`   | Target CPU utilization               | `0.5`        |
| `controller.prometheusUrl`       | Prometheus endpoint                  | (in-cluster) |

## Reproducing the Experiments

```bash
# Load Locust scenarios as ConfigMap
kubectl create configmap locust-scripts \
  --from-file=scripts/locust_burst.py \
  --from-file=scripts/locust_periodic.py \
  --from-file=scripts/locust_onoff.py

# Run the full experiment (~3 hours)
python experiments/run_real_experiments_v3.py

# Analyze and visualize
python experiments/analyze_results.py
python experiments/visualize_results.py
```

Raw results from our run are checked in at `experiments/real_results/real_results.json`.

## Project Structure
.
├── src/                          # Inference service + controller
│   ├── main.py                   # FastAPI service (/predict, /health, /metrics)
│   └── controller.py             # Predictive control loop
├── scripts/
│   ├── locust_burst.py
│   ├── locust_periodic.py
│   ├── locust_onoff.py
│   └── prometheus_converter.py
├── k8s/                          # Kubernetes manifests
├── experiments/                  # Experiment orchestration + analysis
├── charts/timesfm-hpa/           # Helm chart
├── Dockerfile
└── requirements.txt

## Citation

If you use TimesFM-HPA in your research, please cite:

```bibtex
@inproceedings{ulusoy2026timesfmhpa,
  title     = {{TimesFM-HPA}: A Zero-Shot Foundation Model Based Predictive Autoscaler Plugin for {K}ubernetes},
  author    = {Ulusoy, {\.{I}}brahim Enes and Kaynak, Baran},
  booktitle = {Proceedings of [Conference Name]},
  year      = {2026}
}
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Acknowledgments

- [TimesFM](https://github.com/google-research/timesfm) by Google Research
- [Kubernetes](https://kubernetes.io/) and [Prometheus](https://prometheus.io/)
- This work was conducted at Sakarya University, Department of Information Systems Engineering.
