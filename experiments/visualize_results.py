import json
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

with open("experiments/real_results/real_results.json") as f:
    data = json.load(f)

grouped = defaultdict(lambda: {"reactive": [], "predictive": []})
for r in data:
    grouped[r["scenario"]][r["mode"]].append(r)

scenarios = ["burst", "periodic", "onoff"]
scenario_labels = ["Burst", "Periodic", "On-Off"]

# ============================================================
# FIGURE 1: Box plot of p95 latency, per scenario, per mode
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))

positions_r = [1, 4, 7]
positions_p = [2, 5, 8]
data_r = [[x["p95_ms"]/1000.0 for x in grouped[s]["reactive"]] for s in scenarios]
data_p = [[x["p95_ms"]/1000.0 for x in grouped[s]["predictive"]] for s in scenarios]

bp1 = ax.boxplot(data_r, positions=positions_r, widths=0.7, patch_artist=True,
                 boxprops=dict(facecolor='#FF9999', edgecolor='black'),
                 medianprops=dict(color='black', linewidth=2))
bp2 = ax.boxplot(data_p, positions=positions_p, widths=0.7, patch_artist=True,
                 boxprops=dict(facecolor='#99CCFF', edgecolor='black'),
                 medianprops=dict(color='black', linewidth=2))

ax.set_xticks([1.5, 4.5, 7.5])
ax.set_xticklabels(scenario_labels, fontsize=11)
ax.set_ylabel("p95 Response Latency (seconds)", fontsize=11)
ax.set_title("p95 Latency Distribution: Reactive HPA vs. TimesFM-HPA (n=10 each)",
             fontsize=12)
ax.legend([bp1["boxes"][0], bp2["boxes"][0]],
          ["Reactive (HPA)", "Predictive (TimesFM-HPA)"], loc='upper right')
ax.grid(True, axis='y', alpha=0.3)
ax.axhline(y=10, color='red', linestyle='--', alpha=0.5, label='SLA = 10s')
ax.text(8.5, 10.3, 'SLA = 10s', color='red', fontsize=9)
plt.tight_layout()
plt.savefig("experiments/real_results/fig_p95_boxplot.png", dpi=300, bbox_inches='tight')
plt.savefig("experiments/real_results/fig_p95_boxplot.pdf", bbox_inches='tight')
print("Saved: fig_p95_boxplot.png + .pdf")
plt.close()

# ============================================================
# FIGURE 2: Bar chart of mean p95 with std error bars
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))

x = np.arange(len(scenarios))
width = 0.35

means_r = [np.mean(data_r[i]) for i in range(3)]
stds_r = [np.std(data_r[i], ddof=1) for i in range(3)]
means_p = [np.mean(data_p[i]) for i in range(3)]
stds_p = [np.std(data_p[i], ddof=1) for i in range(3)]

bars1 = ax.bar(x - width/2, means_r, width, yerr=stds_r, capsize=5,
               label="Reactive (HPA)", color='#FF9999', edgecolor='black')
bars2 = ax.bar(x + width/2, means_p, width, yerr=stds_p, capsize=5,
               label="Predictive (TimesFM-HPA)", color='#99CCFF', edgecolor='black')

# Iyilesme yuzdesini bar uzerine yaz
for i in range(3):
    delta = (means_r[i] - means_p[i]) / means_r[i] * 100
    y = max(means_r[i] + stds_r[i], means_p[i] + stds_p[i]) + 1
    ax.text(i, y, f"-{delta:.0f}%", ha='center', fontsize=11, fontweight='bold',
            color='green')

ax.set_xticks(x)
ax.set_xticklabels(scenario_labels, fontsize=11)
ax.set_ylabel("Mean p95 Latency (seconds)", fontsize=11)
ax.set_title("Mean p95 Latency by Workload (error bars: ±1 SD, n=10)", fontsize=12)
ax.legend(loc='upper left')
ax.grid(True, axis='y', alpha=0.3)
ax.axhline(y=10, color='red', linestyle='--', alpha=0.5)
ax.text(2.4, 10.3, 'SLA = 10s', color='red', fontsize=9)
plt.tight_layout()
plt.savefig("experiments/real_results/fig_p95_barchart.png", dpi=300, bbox_inches='tight')
plt.savefig("experiments/real_results/fig_p95_barchart.pdf", bbox_inches='tight')
print("Saved: fig_p95_barchart.png + .pdf")
plt.close()

# ============================================================
# FIGURE 3: SLA Violation Rate
# ============================================================
fig, ax = plt.subplots(figsize=(7, 4.5))

SLA = 10000
violations_r = [100 * sum(1 for x in grouped[s]["reactive"] if x["p95_ms"] > SLA) / len(grouped[s]["reactive"]) for s in scenarios]
violations_p = [100 * sum(1 for x in grouped[s]["predictive"] if x["p95_ms"] > SLA) / len(grouped[s]["predictive"]) for s in scenarios]

bars1 = ax.bar(x - width/2, violations_r, width, label="Reactive (HPA)",
               color='#FF9999', edgecolor='black')
bars2 = ax.bar(x + width/2, violations_p, width, label="Predictive (TimesFM-HPA)",
               color='#99CCFF', edgecolor='black')

for i, (vr, vp) in enumerate(zip(violations_r, violations_p)):
    ax.text(i - width/2, vr + 2, f"{vr:.0f}%", ha='center', fontsize=10)
    ax.text(i + width/2, vp + 2, f"{vp:.0f}%", ha='center', fontsize=10)

ax.set_xticks(x)
ax.set_xticklabels(scenario_labels, fontsize=11)
ax.set_ylabel("SLA Violation Rate (%)", fontsize=11)
ax.set_title("Fraction of Runs Violating SLA (p95 > 10s)", fontsize=12)
ax.legend(loc='upper right')
ax.grid(True, axis='y', alpha=0.3)
ax.set_ylim(0, 105)
plt.tight_layout()
plt.savefig("experiments/real_results/fig_sla_violations.png", dpi=300, bbox_inches='tight')
plt.savefig("experiments/real_results/fig_sla_violations.pdf", bbox_inches='tight')
print("Saved: fig_sla_violations.png + .pdf")
plt.close()

print("\nAll figures saved to experiments/real_results/")