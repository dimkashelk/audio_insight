import os, re, logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma-summarizer")

STRICT_INSTRUCTION = (
    "Сделай краткое резюме (до 5 пунктов) и выдели ключевые термины из транскрипта. "
    "Обязательно оба пункта. Пиши без эмоджи, отфильтруй мат, иронию и шутки "
    "(их использование запрещено). Используй нумерованные списки. Пиши текст "
    "сплошной, переносы строки замени на \\n. Мне потребуется этот текст в виде одной строки.\n\n"
)

class SummarizeRequest(BaseModel):
    transcript: str = Field(..., min_length=20, max_length=100000)
    max_tokens: int = Field(default=600, ge=64, le=2048)

class SummarizeResponse(BaseModel):
    summary: str
    model: str
    tokens_used: int


def enforce_format(raw: str) -> str:
    if not raw or not raw.strip():
        return "[DEBUG] Пустой ответ от модели"

    match = re.search(r'1\.\s', raw, re.DOTALL)
    text = raw[match.start():] if match else raw
    text = re.sub(r'<\|im_start\|>.*?<\|im_end\|>', '', raw, flags=re.DOTALL)
    text = re.sub(r'\*\*|\*|__|_|`|#{1,6}', '', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n')
    parts = text.split('\\n\\nКлючевые термины:')
    if len(parts) > 1:
        text = parts[0] + '\\n\\nКлючевые термины:' + parts[1].split('\\n')[0]
    return text.strip()

app = FastAPI(title="AudioInsight ML Service")

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(req: SummarizeRequest):
    full_prompt = f"{STRICT_INSTRUCTION}Транскрипт:\n{req.transcript}"
    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.05,
            "top_p": 0.8,
            "num_predict": req.max_tokens,
            "repeat_penalty": 1.2
        }
    }
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            result = resp.json()
        raw = result.get("response", "")
        cleaned = enforce_format(raw)
        return SummarizeResponse(summary=cleaned, model=MODEL_NAME, tokens_used=result.get("eval_count", 0))
    except httpx.TimeoutException:
        raise HTTPException(504, "Таймаут генерации")
    except Exception as e:
        logger.error(f"ML Error: {e}")
        raise HTTPException(500, f"Ошибка ML-сервиса: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "ollama": OLLAMA_URL}
