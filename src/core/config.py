"""Configuration settings."""

import os
from pathlib import Path
from dotenv import load_dotenv

# путь к .env рядом с корнем репозитория
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../OxxxyBot
DOTENV_PATH = PROJECT_ROOT / ".env"
if not DOTENV_PATH.exists():
    raise FileNotFoundError(f".env not found at: {DOTENV_PATH}")


load_dotenv(DOTENV_PATH, override=True)


BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set.")


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable not set.")


LLM_URL = os.getenv("LLM_URL")
if not LLM_URL:
    raise ValueError("LLM_URL environment variable not set.")


LLM_NAME = os.getenv("LLM_NAME")
if not LLM_NAME:
    raise ValueError("LLM_NAME environment variable not set.")


