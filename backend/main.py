from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import logging
from tasks import process_audio_task, summarize_text_task


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(title="AudioInsight Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0


class ResultResponse(BaseModel):
    result: dict | None = None
    error: str | None = None


class SummarizeTextRequest(BaseModel):
    text: str


@app.post("/upload", response_model=TaskResponse)
async def upload_audio(file: UploadFile = File(...)):
    """Загрузка аудиофайла в очередь обработки"""
    if not file.filename.lower().endswith(('.mp3', '.wav', '.m4a', '.mp4')):
        raise HTTPException(400, "Неподдерживаемый формат. Допустимы: mp3, wav, m4a, mp4")

    filepath = f"{UPLOAD_DIR}/{uuid.uuid4().hex}_{file.filename}"
    with open(filepath, "wb") as f:
        f.write(await file.read())

    task = process_audio_task.delay(filepath, file.filename)
    return TaskResponse(task_id=task.id, status="queued", progress=0)


@app.post("/summarize-text", response_model=TaskResponse)
async def summarize_text(req: SummarizeTextRequest):
    """Прямая генерация резюме по тексту (без транскрибации)"""
    task = summarize_text_task.delay(req.text)
    return TaskResponse(task_id=task.id, status="queued", progress=0)


from tasks import celery_app


@app.get("/status/{task_id}")
def get_status(task_id: str):
    try:
        res = celery_app.AsyncResult(task_id)

        info = {}
        try:
            if res.info and isinstance(res.info, dict):
                info = res.info
        except Exception:
            pass

        status = info.get("status", res.state) if res.state else "PENDING"
        progress = info.get("progress", 0 if status == "PENDING" else 100 if status in ("SUCCESS", "FAILURE") else 50)

        return {
            "task_id": task_id,
            "status": status,
            "progress": progress
        }
    except Exception as e:
        logger.warning(f"Status fallback for {task_id}: {e}")
        return {"task_id": task_id, "status": "UNKNOWN", "progress": 0}


@app.get("/result/{task_id}", response_model=ResultResponse)
def get_result(task_id: str):
    try:
        from tasks import celery_app
        res = celery_app.AsyncResult(task_id)

        if res.state == "PENDING":
            return ResultResponse(result=None, error="Task still processing")
        elif res.state == "SUCCESS":
            return ResultResponse(result=res.result)
        elif res.state == "FAILURE":
            return ResultResponse(result=None, error=str(res.result) if res.result else "Unknown error")
        return ResultResponse(result=None, error=f"Unexpected state: {res.state}")

    except AttributeError as e:
        if "DisabledBackend" in str(e):
            import redis, json
            try:
                r = redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"))
                key = f"celery-task-meta-{task_id}"
                data = r.get(key)
                if data:
                    meta = json.loads(data)
                    if meta.get("status") == "SUCCESS":
                        return ResultResponse(result=meta.get("result"))
                    elif meta.get("status") == "FAILURE":
                        return ResultResponse(result=None, error=str(meta.get("result")))
            except Exception as redis_err:
                logger.warning(f"⚠️ Redis fallback failed: {redis_err}")
            return ResultResponse(result=None, error="Result backend not configured")
        raise
    except Exception as e:
        logger.error(f"Error getting result: {e}")
        return ResultResponse(result=None, error=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
