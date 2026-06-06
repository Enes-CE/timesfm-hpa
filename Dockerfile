FROM python:3.12-slim

WORKDIR /app

# Git ve sistem bağımlılıklarını kur
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# CPU-only torch için özel index URL
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Önce requirements kopyala, sonra kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kaynak kodu kopyala
COPY src/ ./src/
COPY models/ ./models/

# Port
EXPOSE 8001

# Başlatma komutu
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
