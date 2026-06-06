import subprocess, time, json, os, csv, sys
from datetime import datetime

# --- AYARLAR ---
NAMESPACE = "default"
SERVICE_DNS = "http://autoscaler-plugin-svc:8001"  # cluster-internal DNS, port-forward yok
RESULTS_DIR = "experiments/real_results"
DEPLOYMENT = "autoscaler-plugin"
HPA_YAML = "k8s/hpa.yaml"
N_REPEATS = 10
RUN_TIME_SEC = 120
USERS = 10
SPAWN_RATE = 2
COOLDOWN_SEC = 30
LOCUST_IMAGE = "locustio/locust:2.31.5"
SCENARIOS = [
    ("burst",    "locust_burst.py",    "BurstTrafficUser"),
    ("periodic", "locust_periodic.py", "PeriodicTrafficUser"),
    ("onoff",    "locust_onoff.py",    "OnOffTrafficUser"),
]

os.makedirs(RESULTS_DIR, exist_ok=True)

def sh(cmd, check=False, capture=False, timeout=None):
    return subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=True, timeout=timeout)

def reset_replicas():
    print("  [reset] Pod sayisi 1 yapiliyor...")
    sh("kubectl scale deployment " + DEPLOYMENT + " --replicas=1")
    time.sleep(15)

def enable_hpa():
    print("  [hpa] HPA aciliyor...")
    sh("kubectl apply -f " + HPA_YAML)
    time.sleep(10)

def disable_hpa():
    print("  [hpa] HPA siliniyor...")
    sh("kubectl delete hpa autoscaler-plugin-hpa --ignore-not-found=true")
    time.sleep(5)

def warmup():
    print("  [warmup] Model isindiriliyor (pod ici)...")
    pod_name = sh("kubectl get pods -l app=autoscaler-plugin -o jsonpath=\"{.items[0].metadata.name}\"", capture=True).stdout.strip()
    if not pod_name:
        print("  [warmup] Pod bulunamadi, atlaniyor")
        return
    success = 0
    for i in range(5):
        cmd = (
            "kubectl exec " + pod_name + " -- python -c "
            "\"import urllib.request,json; "
            "req=urllib.request.Request('http://localhost:8001/predict',"
            "data=json.dumps({'values':[1,2,3,4,5,6,7,8,9,10],'horizon':5}).encode(),"
            "headers={'Content-Type':'application/json'}); "
            "urllib.request.urlopen(req,timeout=30).read()\""
        )
        try:
            sh(cmd, timeout=45)
            success += 1
        except Exception as e:
            print("    [warmup] istek " + str(i+1) + " basarisiz (devam): " + str(type(e).__name__))
    print("  [warmup] Tamam (" + str(success) + "/5 basarili).")

def cleanup_locust_pod(pod_name):
    sh("kubectl delete pod " + pod_name + " --ignore-not-found=true --wait=false")

def run_locust_in_cluster(scenario, locust_file, user_class, mode, rep):
    tag = scenario + "_" + mode + "_run" + str(rep)
    pod_name = "locust-" + tag.replace("_", "-")
    print("  [locust] " + tag + " pod aciliyor: " + pod_name)

    # Eski pod varsa temizle
    cleanup_locust_pod(pod_name)
    time.sleep(2)

    # Locust pod'u olustur (ConfigMap'ten scriptleri mount et)
    yaml_text = (
"apiVersion: v1\n"
"kind: Pod\n"
"metadata:\n"
"  name: " + pod_name + "\n"
"  labels:\n"
"    app: locust-runner\n"
"spec:\n"
"  restartPolicy: Never\n"
"  containers:\n"
"  - name: locust\n"
"    image: " + LOCUST_IMAGE + "\n"
"    command: [\"sh\", \"-c\"]\n"
"    args:\n"
"    - >\n"
"      locust -f /scripts/" + locust_file +
"      --headless --host " + SERVICE_DNS +
"      --users " + str(USERS) +
"      --spawn-rate " + str(SPAWN_RATE) +
"      --run-time " + str(RUN_TIME_SEC) + "s" +
"      --csv /results/" + tag +
"      --only-summary;" +
"      echo 'LOCUST_DONE';" +
"      sleep 120\n"
"    volumeMounts:\n"
"    - name: scripts\n"
"      mountPath: /scripts\n"
"    - name: results\n"
"      mountPath: /results\n"
"  volumes:\n"
"  - name: scripts\n"
"    configMap:\n"
"      name: locust-scripts\n"
"  - name: results\n"
"    emptyDir: {}\n"
    )

    yaml_path = RESULTS_DIR + "/_tmp_pod.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_text)

    sh("kubectl apply -f " + yaml_path)

    # Pod'un Running'e gelmesini bekle
    for _ in range(30):
        status = sh("kubectl get pod " + pod_name + " -o jsonpath=\"{.status.phase}\"", capture=True).stdout.strip()
        if status in ("Running", "Succeeded", "Failed"):
            break
        time.sleep(2)

    # Locust bitene kadar bekle (log'da LOCUST_DONE arıyoruz)
    print("  [locust] " + tag + " calisiyor (" + str(RUN_TIME_SEC) + "s)...")
    t0 = time.time()
    max_wait = RUN_TIME_SEC + 180
    locust_finished = False
    while time.time() - t0 < max_wait:
        logs = sh("kubectl logs " + pod_name + " --tail=50", capture=True).stdout
        if "LOCUST_DONE" in logs:
            locust_finished = True
            break
        phase = sh("kubectl get pod " + pod_name + " -o jsonpath=\"{.status.phase}\"", capture=True).stdout.strip()
        if phase in ("Failed",):
            break
        time.sleep(5)
    elapsed = int(time.time() - t0)
    print("  [locust] " + tag + " bitti (" + str(elapsed) + "s, finished=" + str(locust_finished) + ")")
    # Pod hala Running, CSV'leri kopyalamak icin zaman var
    time.sleep(3)

    # CSV'leri pod'dan disari kopyala
    csv_local_prefix = RESULTS_DIR + "/" + tag
    sh("kubectl cp " + pod_name + ":/results/" + tag + "_stats.csv " + csv_local_prefix + "_stats.csv")
    sh("kubectl cp " + pod_name + ":/results/" + tag + "_failures.csv " + csv_local_prefix + "_failures.csv")

    # Pod'u sil
    cleanup_locust_pod(pod_name)

    return parse_locust_csv(csv_local_prefix + "_stats.csv", scenario, mode, rep)

def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0

def parse_locust_csv(path, scenario, mode, rep):
    if not os.path.exists(path):
        print("  [parse] CSV bulunamadi: " + path)
        return None
    with open(path) as f:
        for row in csv.DictReader(f):
            if row.get("Name") == "Aggregated":
                return {
                    "scenario": scenario,
                    "mode": mode,
                    "rep": rep,
                    "total_requests": int(safe_float(row.get("Request Count", 0))),
                    "failures": int(safe_float(row.get("Failure Count", 0))),
                    "avg_ms": safe_float(row.get("Average Response Time", 0)),
                    "p50_ms": safe_float(row.get("50%", 0)),
                    "p95_ms": safe_float(row.get("95%", 0)),
                    "p99_ms": safe_float(row.get("99%", 0)),
                    "rps": safe_float(row.get("Requests/s", 0)),
                }
    return None

def main():
    print("=" * 60)
    print("GERCEK DENEY V3 BASLIYOR (pod-ici Locust)")
    print("Zaman: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    total = len(SCENARIOS) * 2 * N_REPEATS
    print("Toplam run sayisi: " + str(total))
    print("Tahmini sure: ~" + str(int(total * (RUN_TIME_SEC + 60) / 60)) + " dakika")
    print("=" * 60)

    # Mevcut sonuclari yukle (kaldigimiz yerden devam et)
    results_path = RESULTS_DIR + "/real_results.json"
    if os.path.exists(results_path):
        with open(results_path) as f:
            all_results = json.load(f)
        print("Mevcut " + str(len(all_results)) + " run yuklendi, kalan run'lar koshturulacak.")
    else:
        all_results = []
    done_keys = set((r["scenario"], r["mode"], r["rep"]) for r in all_results)

    counter = 0

    for mode in ["reactive", "predictive"]:
        print("")
        print("*** MOD: " + mode.upper() + " ***")
        if mode == "reactive":
            disable_hpa()
            enable_hpa()
            print("  >>> HPA aktif, controller KAPALI olmali")
        else:
            disable_hpa()
            print("  >>> HPA KAPALI, controller acik olmali")
            print("  >>> AYRI PENCEREDE: python src/controller.py calistir!")
            input("  Controller calisiyor mu? Enter ile devam et...")

        for scenario, locust_file, user_class in SCENARIOS:
            for rep in range(1, N_REPEATS + 1):
                counter += 1
                print("")
                print("[" + str(counter) + "/" + str(total) + "] " + scenario + " | " + mode + " | run " + str(rep) + "/" + str(N_REPEATS))
                if (scenario, mode, rep) in done_keys:
                    print("  -> ZATEN YAPILDI, atlaniyor")
                    continue
                if mode == "reactive":
                    reset_replicas()
                else:
                    print("  [predictive] reset atlandi, controller yonetir")
                result = run_locust_in_cluster(scenario, locust_file, user_class, mode, rep)
                if result:
                    all_results.append(result)
                    avg = result["avg_ms"]
                    p95 = result["p95_ms"]
                    fail = result["failures"]
                    rps = result["rps"]
                    print("  -> avg=" + str(int(avg)) + "ms p95=" + str(int(p95)) + "ms fail=" + str(fail) + " rps=" + str(round(rps, 2)))
                else:
                    print("  -> SONUC ALINAMADI")
                cooldown = 60 if mode == "predictive" else COOLDOWN_SEC
                time.sleep(cooldown)
                with open(RESULTS_DIR + "/real_results.json", "w") as f:
                    json.dump(all_results, f, indent=2)

    print("")
    print("=" * 60)
    print("TUM DENEYLER BITTI")
    print("Sonuc dosyasi: " + RESULTS_DIR + "/real_results.json")
    print("Toplam basarili run: " + str(len(all_results)) + "/" + str(total))
    print("=" * 60)


if __name__ == "__main__":
    main()