from locust import HttpUser, task, between
import random
import math
import time


class PeriodicTrafficUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def predict(self):
        t = time.time()
        amplitude = 50 + 40 * math.sin(2 * math.pi * t / 60)
        values = [amplitude + random.gauss(0, 5) for _ in range(20)]
        self.client.post("/predict", json={"values": values, "horizon": 5})