# backend/tasks.py
import os
import logging
from celery import Celery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml-service:8001")

celery_app = Celery("tasks", broker=CELERY_BROKER_URL)
celery_app.conf.result_backend = CELERY_BROKER_URL
celery_app.conf.task_track_started = True
celery_app.conf.result_expires = 3600

@celery_app.task(bind=True)
def process_audio_task(self, filepath: str, filename: str):
    # TODO
    pass


@celery_app.task(bind=True)
def summarize_text_task(self, text: str):
    # TODO
    pass
