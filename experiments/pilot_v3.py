import sys
sys.path.insert(0, "experiments")
from run_real_experiments_v3 import (
    enable_hpa, disable_hpa, reset_replicas, warmup,
    run_locust_in_cluster, SCENARIOS
)

# Sadece burst + 1 run + reactive mod
print("=" * 60)
print("PILOT V3: tek run, sistem cluster-ici Locust test ediyor")
print("=" * 60)

# Reactive mod kur
disable_hpa()
enable_hpa()

# Bir burst run koştur
scenario, locust_file, user_class = SCENARIOS[0]  # burst
reset_replicas()
result = run_locust_in_cluster(scenario, locust_file, user_class, "reactive", 0)

print("")
print("=" * 60)
if result:
    print("PILOT BASARILI")
    print("Sonuc: " + str(result))
else:
    print("PILOT BASARISIZ — sonuc alinamadi")
print("=" * 60)