FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /root/.cache/whisper uploads

CMD sh -c "uvicorn main:app --host 0.0.0.0 --port 8000 & \
           celery -A tasks.celery_app worker --loglevel=info --pool=solo"
