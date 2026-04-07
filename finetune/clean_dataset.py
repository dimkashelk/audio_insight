import json
import re


def is_structured(text: str) -> bool:
    has_list = bool(re.search(r'^\d+\.', text, re.MULTILINE))
    has_terms = bool(re.search(r'(термины|ключевые|понятия)', text, re.IGNORECASE))
    return has_list and has_terms


def clean_dataset(input_path: str, output_path: str):
    kept, skipped = 0, 0
    with open(input_path, "r", encoding="utf-8") as fin, \
            open(output_path, "w", encoding="utf-8") as fout:

        seen_completions = set()
        for line in fin:
            item = json.loads(line.strip())
            comp = item.get("completion", "").strip()

            if comp in seen_completions:
                skipped += 1
                continue
            seen_completions.add(comp)

            if not is_structured(comp) or len(comp) < 30:
                skipped += 1
                continue

            fout.write(line)
            kept += 1

    print(f"Оставлено: {kept} примеров | Удалено: {skipped} (повторы/мусор)")


for name in ["train", "test"]:
    clean_dataset(f"data/{name}.jsonl", f"data/{name}_clean.jsonl")
    import os

    os.replace(f"data/{name}_clean.jsonl", f"data/{name}.jsonl")
