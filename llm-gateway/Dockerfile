FROM python:3.9-slim

WORKDIR /app

# Instalar herramientas de compilación necesarias para llama-cpp-python
RUN apt-get update && apt-get install -y gcc g++ cmake build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install prometheus_client
RUN python -m nltk.downloader punkt || true

COPY documents/ ./documents/
COPY gateway.py .

EXPOSE 8000

CMD ["uvicorn", "gateway:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]