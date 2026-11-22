FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 1. Dependencies — cached independently from source code
COPY requirements.txt ./

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 2. Application source
COPY . .

# 3. Project installation with monitoring extras
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e '.[monitoring]' debugpy

EXPOSE 8000 5678