# API FastAPI (Capas 2-3-4)
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libgomp1: lo necesitan LightGBM y XGBoost · fonts-dejavu: fuente del CAPTCHA
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.lock.txt .
RUN pip install -r requirements.lock.txt

COPY app ./app
COPY crear_admin.py .

# Usuario sin privilegios
RUN useradd --create-home api
USER api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fs http://localhost:8000/salud || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
