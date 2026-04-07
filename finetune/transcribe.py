import os
import sys
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import whisper
import torch


VIDEOS_DIR = Path("videos")
TRANSCRIPTION_DIR = Path("transcription")
MODEL_SIZE = "turbo"
LANGUAGE = "ru"


_worker_model = None
_worker_device = None
_worker_lang = None


def get_optimal_device():
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_safe_workers():
    try:
        total_ram_gb = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024 ** 3)
    except (AttributeError, ValueError):
        total_ram_gb = 16.0
    return 2
    if total_ram_gb < 12:
        return 2
    elif total_ram_gb < 24:
        return 3
    return min(4, multiprocessing.cpu_count() // 2)


def init_worker(model_size, device, language):
    global _worker_model, _worker_device, _worker_lang
    _worker_device = device
    _worker_lang = language
    _worker_model = whisper.load_model(model_size, device=device)


def process_file(file_path):
    try:
        result = _worker_model.transcribe(
            str(file_path),
            language=_worker_lang,
            verbose=False,
            fp16=(_worker_device != "cpu")
        )
        output_file = TRANSCRIPTION_DIR / f"{Path(file_path).stem}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["text"].strip())

        if _worker_device == "mps":
            torch.mps.empty_cache()

        return (file_path.name, True, None)
    except Exception as e:
        return (file_path.name, False, str(e))


def main():
    if sys.platform == "darwin":
        multiprocessing.set_start_method('spawn', force=True)

    if not VIDEOS_DIR.exists():
        print(f"Папка '{VIDEOS_DIR.name}' не найдена рядом со скриптом.")
        return

    TRANSCRIPTION_DIR.mkdir(exist_ok=True)
    device = get_optimal_device()
    max_workers = get_safe_workers()

    print(f"Устройство: {device.upper()} | Модель: {MODEL_SIZE} | Воркеров: {max_workers}")
    print("Инициализация пула процессов (модель загрузится в каждый процесс)...")

    SUPPORTED_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wav", ".mp3", ".m4a", ".webm", ".flv", ".ogg"}
    files = sorted([f for f in VIDEOS_DIR.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXT])

    if not files:
        print("В папке 'videos' нет поддерживаемых файлов.")
        return

    print(f"Найдено файлов: {len(files)}. Запуск параллельной транскрипции...\n")

    with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=init_worker,
            initargs=(MODEL_SIZE, device, LANGUAGE)
    ) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        completed = 0
        for future in as_completed(futures):
            name, success, error = future.result()
            completed += 1
            if success:
                print(f"[{completed}/{len(files)}] {name}")
            else:
                print(f"[{completed}/{len(files)}] {name} → {error}")

    print("\nВсе файлы обработаны")


if __name__ == "__main__":
    main()
