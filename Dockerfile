# Dockerfile – Versión con API REST
FROM python:3.12-slim

LABEL maintainer="tu@email.com"
LABEL version="2025.11.18-api"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn python-dotenv fastapi

COPY seo_pipeline ./seo_pipeline
COPY api ./api
COPY client_manager.py .
COPY .env.example .env

RUN chown -R appuser:appuser /app
USER appuser

VOLUME ["/app/config", "/app/runs", "/app/credentials"]

EXPOSE 8000

# Por defecto arranca la API (puedes sobrescribir con client_manager.py si quieres)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]