from locust import HttpUser, task, between
import random


class BurstTrafficUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def predict(self):
        values = [random.uniform(10, 100) for _ in range(20)]
        self.client.post("/predict", json={"values": values, "horizon": 5})