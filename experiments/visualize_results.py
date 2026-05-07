import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Sonuclari yukle
df = pd.read_csv("experiments/results.csv")

# Renk paleti
colors = {
    "TimesFM": "#036bfc",
    "LightGBM": "#0ff0b3",
    "Reaktif": "#ff4444"
}

fig, axes = plt.subplots(1, 3, figsize=(18, 6))
fig.suptitle("Predictive Auto-Scaling: Karsilastirmali Deney Sonuclari", 
             fontsize=16, fontweight="bold", y=1.02)

traffic_types = ["Periyodik", "Burst", "OnOff"]
strategies = ["TimesFM", "LightGBM", "Reaktif"]
x = np.arange(len(traffic_types))
width = 0.25

# ── Grafik 1: Ortalama Yanıt Süresi ──
ax1 = axes[0]
for i, strategy in enumerate(strategies):
    vals = [df[(df.traffic==t) & (df.strategy==strategy)]["avg_response_ms"].values[0] 
            for t in traffic_types]
    ax1.bar(x + i*width, vals, width, label=strategy, color=colors[strategy], alpha=0.85)

ax1.set_title("Ortalama Yanis Suresi (ms)", fontweight="bold")
ax1.set_ylabel("ms")
ax1.set_xticks(x + width)
ax1.set_xticklabels(traffic_types)
ax1.axhline(y=1000, color="red", linestyle="--", alpha=0.5, label="SLA Esigi (1000ms)")
ax1.legend()
ax1.grid(axis="y", alpha=0.3)

# ── Grafik 2: SLA İhlal Oranı ──
ax2 = axes[1]
for i, strategy in enumerate(strategies):
    vals = [df[(df.traffic==t) & (df.strategy==strategy)]["sla_violation_pct"].values[0] 
            for t in traffic_types]
    ax2.bar(x + i*width, vals, width, label=strategy, color=colors[strategy], alpha=0.85)

ax2.set_title("SLA Ihlal Orani (%)", fontweight="bold")
ax2.set_ylabel("%")
ax2.set_xticks(x + width)
ax2.set_xticklabels(traffic_types)
ax2.legend()
ax2.grid(axis="y", alpha=0.3)

# ── Grafik 3: Ortalama Pod Sayısı ──
ax3 = axes[2]
for i, strategy in enumerate(strategies):
    vals = [df[(df.traffic==t) & (df.strategy==strategy)]["avg_pods"].values[0] 
            for t in traffic_types]
    ax3.bar(x + i*width, vals, width, label=strategy, color=colors[strategy], alpha=0.85)

ax3.set_title("Ortalama Pod Sayisi (Maliyet)", fontweight="bold")
ax3.set_ylabel("Pod Sayisi")
ax3.set_xticks(x + width)
ax3.set_xticklabels(traffic_types)
ax3.legend()
ax3.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig("experiments/results_chart.png", dpi=150, bbox_inches="tight")
print("Grafik kaydedildi: experiments/results_chart.png")

# ── Ozet Tablosu ──
print("\n" + "=" * 60)
print("OZET: TimesFM vs Reaktif HPA")
print("=" * 60)
for traffic in traffic_types:
    timesfm_sla = df[(df.traffic==traffic) & (df.strategy=="TimesFM")]["sla_violation_pct"].values[0]
    reaktif_sla = df[(df.traffic==traffic) & (df.strategy=="Reaktif")]["sla_violation_pct"].values[0]
    improvement = reaktif_sla - timesfm_sla
    print(f"{traffic:12} | Reaktif: %{reaktif_sla:.1f} | TimesFM: %{timesfm_sla:.1f} | Iyilesme: %{improvement:.1f}")
