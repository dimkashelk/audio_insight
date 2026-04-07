import json
import os
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional


CONFIG = {
    "input_dir": "transcription",
    "output_dir": "data",
    "chunk_size_tokens": 2000,
    "chunk_overlap_tokens": 200,

    "api_url": "http://127.0.0.1:1234/api/v1/chat",
    "model_name": "google/gemma-3-12b",
    "api_timeout": 120,
    "max_retries": 3,
    "retry_delay": 5,

    "system_prompt": "Ты — ассистент для обработки учебных материалов. Отвечай строго по инструкции.",
    "user_prompt": "Сделай краткое резюме (до 5 пунктов) и выдели ключевые термины из транскрипта. Обязательно оба пункта. Пиши без эмоджи, отфлильтруй мат, иронию и шутки (их использование запрещено). Используй нумерованные списки. Пиши текст сплошной, переносы строки замени на \\n. Мне потребуется этот текст в виде одной строки.",

    "test_split_ratio": 0.15,
    "seed": 42,
}


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    if estimate_tokens(text) <= chunk_size:
        return [text]

    chunks = []
    chunk_chars = chunk_size * 4
    overlap_chars = overlap * 4

    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))

        if end < len(text):
            cut_point = -1
            for punct in ['.\n', '. ', '!\n', '! ', '?\n', '? ', '\n\n']:
                pos = text.rfind(punct, start + chunk_chars - 300, end)
                if pos > start + chunk_chars - 300 and pos > cut_point:
                    cut_point = pos + len(punct) - 1

            if cut_point > start:
                end = cut_point + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        next_start = end - overlap_chars if end < len(text) else end
        start = max(next_start, start + 1)

    return chunks


def call_gemma_api(transcript_chunk: str, config: Dict) -> Optional[str]:
    payload = {
        "model": config["model_name"],
        "system_prompt": config["system_prompt"],
        "input": f"{config['user_prompt']}\n\nТранскрипт:\n{transcript_chunk}"
    }

    for attempt in range(config["max_retries"]):
        try:
            response = requests.post(
                config["api_url"],
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=config["api_timeout"]
            )
            response.raise_for_status()
            data = response.json()

            if "output" in data and len(data["output"]) > 0:
                content = data["output"][0].get("content", "")
                content = content.replace('\n\n', '\n').strip()
                return content
            else:
                print(f"Неожиданный формат ответа: {data.keys()}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Попытка {attempt + 1}/{config['max_retries']} failed: {e}")
            if attempt < config["max_retries"] - 1:
                time.sleep(config["retry_delay"] * (attempt + 1))  # Exponential backoff
            else:
                print(f"Не удалось получить ответ после {config['max_retries']} попыток")
                return None
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}")
            return None

    return None


def format_for_mlx(prompt: str, completion: str) -> Dict:
    return {
        "prompt": prompt,
        "completion": completion
    }


def load_transcripts(input_dir: str) -> List[Dict[str, str]]:
    transcripts = []
    input_path = Path(input_dir)

    if not input_path.exists():
        print(f"Папка {input_dir} не найдена")
        return transcripts

    for file_path in input_path.glob("*.txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
                if text:
                    transcripts.append({"filename": file_path.name, "text": text})
                    print(f"Загружен: {file_path.name} ({len(text)} симв.)")
        except Exception as e:
            print(f"Ошибка чтения {file_path}: {e}")

    return transcripts


def main():
    print("Запуск генерации датасета для Qwen2.5-1.5B LoRA")
    print(f"Вход: {CONFIG['input_dir']}, Выход: {CONFIG['output_dir']}")
    print(f"API: {CONFIG['api_url']} ({CONFIG['model_name']})")
    print("-" * 60)

    os.makedirs(CONFIG["output_dir"], exist_ok=True)

    transcripts = load_transcripts(CONFIG["input_dir"])
    if not transcripts:
        print("Нет файлов для обработки. Завершаю.")
        return

    all_samples = []

    for doc in transcripts:
        print(f"\nОбработка: {doc['filename']}")

        chunks = chunk_text(
            doc["text"],
            CONFIG["chunk_size_tokens"],
            CONFIG["chunk_overlap_tokens"]
        )
        print(f"   Разбито на {len(chunks)} чанков")

        for i, chunk in enumerate(chunks, 1):
            print(f"       Чанк {i}/{len(chunks)} ({estimate_tokens(chunk)} ток.)", end=" ... ")

            completion = call_gemma_api(chunk, CONFIG)

            if completion:
                full_prompt = f"{CONFIG['user_prompt']}\n\nТранскрипт:\n{chunk[:500]}..." if len(
                    chunk) > 500 else f"{CONFIG['user_prompt']}\n\nТранскрипт:\n{chunk}"

                sample = format_for_mlx(full_prompt, completion)
                all_samples.append(sample)
                print("Готово")
            else:
                print("ПРОПУЩЕН")

        time.sleep(2)

    print(f"\nИтого: {len(all_samples)} пар промпт→ответ")
    if not all_samples:
        print("Нет данных для сохранения. Проверь логи выше.")
        return

    import random
    random.seed(CONFIG["seed"])
    random.shuffle(all_samples)

    split_idx = int(len(all_samples) * (1 - CONFIG["test_split_ratio"]))
    train_samples = all_samples[:split_idx]
    test_samples = all_samples[split_idx:]

    def save_jsonl(samples: List[Dict], filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    train_path = os.path.join(CONFIG["output_dir"], "train.jsonl")
    test_path = os.path.join(CONFIG["output_dir"], "test.jsonl")

    save_jsonl(train_samples, train_path)
    save_jsonl(test_samples, test_path)

    print(f"\nГотово!")
    print(f"      {train_path}: {len(train_samples)} примеров")
    print(f"      {test_path}: {len(test_samples)} примеров")


if __name__ == "__main__":
    main()
