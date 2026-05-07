from locust import HttpUser, task, between
import random
import math
import time

class PredictUser(HttpUser):
    wait_time = between(1, 3)
    
    def generate_timeseries(self):
        """20 noktalık zaman serisi üretir"""
        return [float(random.randint(10, 200)) for _ in range(20)]
    
    @task
    def predict(self):
        payload = {
            "values": self.generate_timeseries(),
            "horizon": 5
        }
        self.client.post("/predict", json=payload)


class PeriodicTrafficUser(HttpUser):
    """Dönemsel trafik: sinüs dalgası pattern"""
    wait_time = between(0.5, 1.5)
    
    @task
    def predict_periodic(self):
        t = time.time()
        amplitude = 50 + 40 * math.sin(2 * math.pi * t / 60)
        values = [amplitude + random.gauss(0, 5) for _ in range(20)]
        self.client.post("/predict", json={"values": values, "horizon": 5})


class BurstTrafficUser(HttpUser):
    """Burst trafik: ani yük artışı"""
    wait_time = between(0.1, 0.5)
    
    @task
    def predict_burst(self):
        values = [random.uniform(80, 120) for _ in range(20)]
        self.client.post("/predict", json={"values": values, "horizon": 5})


class OnOffTrafficUser(HttpUser):
    """On-Off trafik: açık/kapalı pattern"""
    wait_time = between(1, 2)
    
    @task
    def predict_onoff(self):
        t = int(time.time())
        if (t // 30) % 2 == 0:
            values = [random.uniform(90, 110) for _ in range(20)]
        else:
            values = [random.uniform(1, 5) for _ in range(20)]
        self.client.post("/predict", json={"values": values, "horizon": 5})
