from locust import HttpUser, task, between
import random
import time


class OnOffTrafficUser(HttpUser):
    wait_time = between(0.5, 1)

    @task
    def predict(self):
        t = int(time.time())
        if (t // 30) % 2 == 0:
            values = [random.uniform(80, 120) for _ in range(20)]
        else:
            values = [random.uniform(1, 5) for _ in range(20)]
        self.client.post("/predict", json={"values": values, "horizon": 5})