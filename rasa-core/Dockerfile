# Dockerfile para el microservicio rasa-core
FROM python:3.10-slim

# Actualizar e instalar dependencias del sistema
RUN apt-get update && apt-get install -y gcc libssl-dev curl build-essential libffi-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# <<-- Agregar esta línea para descargar el modelo spaCy
RUN python -m spacy download es_core_news_md

# Copiar archivos de configuración y variables de entorno
COPY config.yml .
COPY credentials.yml .
COPY domain.yml .
COPY endpoints.yml .
COPY .env .

# Copiar la carpeta de datos de entrenamiento
COPY data/ ./data

# Copiar el directorio de acciones personalizadas
COPY actions/ ./actions

# Copiar el directorio de modelos entrenados (si lo tienes)
COPY models/ ./models

# Comando para iniciar el servidor de Rasa
CMD ["rasa", "run", "--enable-api", "--cors", "*", "--ports", "5005"]