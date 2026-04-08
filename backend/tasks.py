# backend/tasks.py
import os
import logging
from celery import Celery
import whisper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml-service:8001")

celery_app = Celery("tasks", broker=CELERY_BROKER_URL)
celery_app.conf.result_backend = CELERY_BROKER_URL
celery_app.conf.task_track_started = True
celery_app.conf.result_expires = 3600


# === Глобальные переменные для воркера ===
_worker_model = None
_worker_device = None


def get_optimal_device():
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


WHISPER_CACHE_DIR = os.getenv("WHISPER_CACHE_DIR", "/root/.cache/whisper")

def init_whisper_worker():
    global _worker_model, _worker_device
    _worker_device = get_optimal_device()
    model_size = os.getenv("WHISPER_MODEL", "turbo")
    logger.info(f"Загрузка Whisper '{model_size}' из {WHISPER_CACHE_DIR}...")
    _worker_model = whisper.load_model(model_size, device=_worker_device, download_root=WHISPER_CACHE_DIR)
    logger.info("Модель загружена")


@celery_app.task(bind=True)
def process_audio_task(self, filepath: str, filename: str):
    # TODO
    pass


@celery_app.task(bind=True)
def summarize_text_task(self, text: str):
    # TODO
    pass
