# One Python image for Burbot API, migration initializer, Prefect Server and Worker.
# Unlike Dockerfile.monitoring, MinIO uses the existing Chainguard image in Compose.
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
COPY pyproject.toml ./
COPY . .

# Keep legacy dependencies and add Prefect 3 + boto3 from the project extras.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e '.[monitoring]' debugpy

EXPOSE 8000 5678
