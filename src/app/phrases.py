from random import randint
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHRASES_PATH = PROJECT_ROOT / "src/app/phrases.txt"

def reload_phrases() -> list[str]:
    with PHRASES_PATH.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return [line.replace("\\n", "\n").rstrip("\n") for line in lines]

def return_punch(phrases: list[str]) -> tuple[str, list[str]]:
    if phrases:
        idx = randint(0, len(phrases) - 1)
        punch = phrases.pop(idx)
        return punch, phrases
    updated = reload_phrases()
    return return_punch(updated)