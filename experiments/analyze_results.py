import json
import numpy as np
from scipy import stats
from collections import defaultdict

# Sonuclari yukle
with open("experiments/real_results/real_results.json") as f:
    data = json.load(f)

print(f"Toplam run sayisi: {len(data)}")
print(f"Reactive runs: {sum(1 for r in data if r['mode']=='reactive')}")
print(f"Predictive runs: {sum(1 for r in data if r['mode']=='predictive')}")
print("=" * 75)

# Senaryo bazli grupla
SLA_THRESHOLD_MS = 10000.0
grouped = defaultdict(lambda: {"reactive": [], "predictive": []})
for r in data:
    grouped[r["scenario"]][r["mode"]].append(r)

# Her senaryo icin analiz
for scenario in ["burst", "periodic", "onoff"]:
    print(f"\n### {scenario.upper()} ###")
    print("-" * 75)
    r_runs = grouped[scenario]["reactive"]
    p_runs = grouped[scenario]["predictive"]

    print(f"n_reactive = {len(r_runs)}, n_predictive = {len(p_runs)}")

    for metric in ["avg_ms", "p95_ms", "p99_ms", "rps"]:
        r_vals = np.array([x[metric] for x in r_runs])
        p_vals = np.array([x[metric] for x in p_runs])

        r_mean, r_std = r_vals.mean(), r_vals.std(ddof=1)
        p_mean, p_std = p_vals.mean(), p_vals.std(ddof=1)

        # Welch's t-test
        t_stat, p_val = stats.ttest_ind(r_vals, p_vals, equal_var=False)

        # Iyilesme yuzdesi (latency icin: reactive - predictive / reactive)
        # rps icin tersi: yuksek olan iyi
        if metric == "rps":
            delta = ((p_mean - r_mean) / r_mean) * 100
        else:
            delta = ((r_mean - p_mean) / r_mean) * 100

        print(f"  {metric:10s}: reactive = {r_mean:8.1f} +/- {r_std:7.1f}  |  "
              f"predictive = {p_mean:8.1f} +/- {p_std:7.1f}  |  "
              f"delta = {delta:+6.1f}%  |  p = {p_val:.4f}")

    # SLA Violation Rate (sadece latency icin anlamli)
    # Locust p95 zaten quantile, ama violation rate'i farkli tanimliyoruz:
    # her run icin: avg_ms > SLA esik mi? Burada total_requests * (1 - cdf) yapamiyoruz
    # cunku biz raw latency dagilimi yerine percentile gozlemlemis durumdayiz.
    # Yaklasik olarak p95 > esik mi sayisini sayalim. Bu yaklasik bir SLA proxy.
    # Daha kesin olabilirdi: per-run failures + p95 esik ihlali
    r_violations = sum(1 for x in r_runs if x["p95_ms"] > SLA_THRESHOLD_MS)
    p_violations = sum(1 for x in p_runs if x["p95_ms"] > SLA_THRESHOLD_MS)
    print(f"  SLA Violations (p95>{int(SLA_THRESHOLD_MS)}ms): "
          f"reactive = {r_violations}/{len(r_runs)} ({100*r_violations/len(r_runs):.0f}%)  |  "
          f"predictive = {p_violations}/{len(p_runs)} ({100*p_violations/len(p_runs):.0f}%)")

    # Failure count
    r_fails = sum(x["failures"] for x in r_runs)
    p_fails = sum(x["failures"] for x in p_runs)
    print(f"  Total Failures: reactive = {r_fails}  |  predictive = {p_fails}")

print("\n" + "=" * 75)
print("ANALIZ TAMAMLANDI")