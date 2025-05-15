# Base image
FROM python:3.10-slim

# Configurar zona horaria de Santiago
ENV TZ=America/Santiago
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Configuración del directorio de trabajo
WORKDIR /app

# Copiar archivos del proyecto (sin generate_appointments.py)
COPY requirements.txt ./
COPY app.py ./
COPY tasks.py ./

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt && pip install gunicorn

# Crear directorio para Prometheus multiproceso
RUN mkdir -p /tmp/prometheus_multiproc_dir
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc_dir

# Configurar punto de entrada
EXPOSE 6001

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:6001", "app:app"]