# Dockerfile para Sonde Tracker
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Usuario no-root
RUN useradd -m -u 1000 appuser
WORKDIR /app

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY src/ ./src/
COPY config/config.example.yaml ./config/config.yaml

# Cambiar a usuario no-root
USER appuser

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Comando por defecto
CMD ["python", "-m", "src.main"]