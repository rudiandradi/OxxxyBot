from random import randint
from pathlib import Path
import random
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHRASES_PATH = PROJECT_ROOT / "src/app/phrases.txt"


def reload_phrases() -> list[str]:
    """Читает архив панчей из файла."""
    with PHRASES_PATH.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return [line.replace("\\n", "\n").rstrip("\n") for line in lines]


def return_punch(phrases: list[str]) -> tuple[str, list[str]]:
    """Возвращает случайный панч и обновлённый список."""
    if phrases:
        idx = randint(0, len(phrases) - 1)
        punch = phrases.pop(idx)
        return punch, phrases
    updated = reload_phrases()
    return return_punch(updated)


def sample_examples(n: int = 10) -> str:
    """
    Возвращает случайные n строк из архива для промпта LLM,
    исключая строки со словами-сравнениями ('как', 'будто', 'словно') для предотвращения имитации ИИ шаблонов.
    """
    lines = reload_phrases()
    filtered_lines = [
        line for line in lines
        if not re.search(r"\b(как|будто|словно)\b", line.lower())
    ]
    # Если вдруг отфильтрованных строк не хватает, берем обычные
    lines_to_sample = filtered_lines if len(filtered_lines) >= n else lines
    if len(lines_to_sample) <= n:
        return "\n".join(lines_to_sample)
    return "\n".join(random.sample(lines_to_sample, n))