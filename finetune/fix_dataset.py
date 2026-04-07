import json
from pathlib import Path


def convert_file(input_path: str, output_path: str):
    with open(input_path, "r", encoding="utf-8") as fin, \
            open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            item = json.loads(line.strip())

            instruction = item.get("instruction", "")
            input_text = item.get("input", "")
            full_prompt = f"{instruction}\n\nКонтекст: {input_text}".strip() if input_text else instruction

            converted = {
                "prompt": full_prompt,
                "completion": item.get("output", "")
            }
            fout.write(json.dumps(converted, ensure_ascii=False) + "\n")


for name in ["train", "test"]:
    convert_file(f"data/{name}.jsonl", f"data/{name}_fixed.jsonl")
    print(f"Конвертирован data/{name}.jsonl")


import os

for name in ["train", "test"]:
    os.replace(f"data/{name}_fixed.jsonl", f"data/{name}.jsonl")
print("Готово! Теперь можно запускать обучение.")
