# Usar una imagen base ligera de Python
FROM python:3.9-slim

# Configurar zona horaria para evitar errores
ENV TZ=America/Chile/Santiago
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Crear usuario no root
RUN useradd -m -d /home/appuser -s /bin/bash appuser

# Instalar dependencias
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código y configuraciones
COPY . .
RUN mkdir -p /app/data && touch /app/data/reclamos.json && chmod 600 /app/data/reclamos.json && chown appuser:appuser /app/data/reclamos.json

# Eliminar archivos sensibles si existen
RUN rm -f .env config.env

# Cambiar permisos de trabajo
RUN chown -R appuser:appuser /app

# Exponer puerto
EXPOSE 7000

# Cambiar a usuario no root
USER appuser

# Ejecutar la aplicación con Gunicorn
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:7000", "--timeout", "120", "--preload", "complaints_api:app"]