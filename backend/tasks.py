import os
import sys
import logging
import multiprocessing
from celery import Celery
import whisper
import torch
import httpx


if sys.platform == "darwin":
    multiprocessing.set_start_method('spawn', force=True)


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


def transcribe_audio(filepath: str) -> list[dict]:
    """Транскрибация с возвратом сегментов (совместимо с форматом UI)"""
    global _worker_model

    if _worker_model is None:
        init_whisper_worker()

    result = _worker_model.transcribe(
        filepath,
        language="ru",
        verbose=False,
        fp16=(_worker_device != "cpu")
    )

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg.get("start", 0), 2),
            "end": round(seg.get("end", 0), 2),
            "text": seg.get("text", "").strip()
        })

    if _worker_device == "mps":
        torch.mps.empty_cache()

    return segments


@celery_app.task(bind=True)
def process_audio_task(self, filepath: str, filename: str):
    try:
        self.update_state(state="PROGRESS", meta={"progress": 10, "status": "Инициализация..."})

        self.update_state(state="PROGRESS", meta={"progress": 30, "status": "Распознавание речи (Whisper)..."})
        transcript = transcribe_audio(filepath)
        full_text = " ".join(seg["text"] for seg in transcript)
        logger.info(f"Транскрибация: {len(transcript)} сегментов, {len(full_text)} символов")

        self.update_state(state="PROGRESS", meta={"progress": 70, "status": "Генерация анализа (Gemma-3-12B)..."})

        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                f"{ML_SERVICE_URL}/summarize",
                json={"transcript": full_text, "max_tokens": 600}
            )
            resp.raise_for_status()
            ml_result = resp.json()

        self.update_state(state="PROGRESS", meta={"progress": 100, "status": "Готово!"})
        logger.info("Задача завершена успешно")

        if os.path.exists(filepath):
            os.remove(filepath)

        return {
            "filename": filename,
            "transcript": transcript,
            "summary": ml_result["summary"],
            "model_used": ml_result["model"],
            "tokens_used": ml_result.get("tokens_used", 0)
        }

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        logger.error(f"❌ HTTP ошибка: {error_msg}")
        self.update_state(state="FAILURE", meta={"status": f"Ошибка API: {error_msg}"})
        return {"error": error_msg}

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:300]}"
        logger.error(f"❌ Ошибка в task: {error_msg}", exc_info=True)
        self.update_state(state="FAILURE", meta={"status": error_msg})
        return {"error": error_msg}


@celery_app.task(bind=True)
def summarize_text_task(self, text: str):
    try:
        self.update_state(state="PROGRESS", meta={"progress": 50, "status": "Генерация..."})

        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{ML_SERVICE_URL}/summarize",
                json={"transcript": text, "max_tokens": 600}
            )
            resp.raise_for_status()
            result = resp.json()

        self.update_state(state="PROGRESS", meta={"progress": 100, "status": "Готово!"})
        return {"summary": result["summary"], "model_used": result["model"]}

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        logger.error(f"HTTP ошибка: {error_msg}")
        self.update_state(state="FAILURE", meta={"status": f"Ошибка API: {error_msg}"})
        return {"error": error_msg}

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:300]}"
        logger.error(f"Ошибка: {error_msg}")
        self.update_state(state="FAILURE", meta={"status": error_msg})
        return {"error": error_msg}
