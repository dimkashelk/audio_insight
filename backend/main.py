from fastapi import FastAPI

app = FastAPI(title="AudioInsight Backend", version="1.0.0")


@app.post("/upload", response_model=TaskResponse)
async def upload_audio(file: UploadFile = File(...)):
    pass


@app.post("/summarize-text", response_model=TaskResponse)
async def summarize_text(req: SummarizeTextRequest):
    pass


@app.get("/status/{task_id}")
def get_status(task_id: str):
    pass

@app.get("/result/{task_id}", response_model=ResultResponse)
def get_result(task_id: str):
    pass


@app.get("/health")
def health():
    pass

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
