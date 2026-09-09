FROM python:3.14

WORKDIR /app

COPY requirements.txt .
COPY . .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install debugpy

EXPOSE 8000