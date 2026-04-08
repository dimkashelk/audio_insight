from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os


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
    # TODO process_audio_task
    pass


@app.post("/summarize-text", response_model=TaskResponse)
async def summarize_text(req: SummarizeTextRequest):
    # TODO summarize_text_task
    pass


@app.get("/status/{task_id}")
def get_status(task_id: str):
    # TODO celery_app
    pass


@app.get("/result/{task_id}", response_model=ResultResponse)
def get_result(task_id: str):
    # TODO celery_app
    pass


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
