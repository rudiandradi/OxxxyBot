import logging
import time
import re
from collections import OrderedDict
from openai import OpenAI
from openai import APIConnectionError, RateLimitError, APIStatusError

from src.core.config import MISTRAL_API_KEY, LLM_URL, LLM_NAME, PROJECT_ROOT
from src.app.text_utils import sanitize_punch
from src.app.phrases import sample_examples

logger = logging.getLogger(__name__)


def get_client() -> OpenAI:
    """Создаёт клиента Mistral с общим HTTP-дедлайном."""
    logger.info(f"Connecting to LLM model {LLM_NAME} via Mistral…")
    return OpenAI(
        api_key=MISTRAL_API_KEY,
        base_url=LLM_URL,
        timeout=15.0,
    )


# ——— лёгкий TTL-LRU кэш для inline-режима ———
class TTLCache:
    def __init__(self, maxsize: int = 128, ttl: int = 15):
        self.maxsize = maxsize
        self.ttl = ttl
        self.data: OrderedDict = OrderedDict()

    def get(self, key):
        now = time.time()
        item = self.data.get(key)
        if not item:
            return None
        value, ts = item
        if now - ts > self.ttl:
            self.data.pop(key, None)
            return None
        self.data.move_to_end(key)
        return value

    def set(self, key, value):
        self.data[key] = (value, time.time())
        self.data.move_to_end(key)
        if len(self.data) > self.maxsize:
            self.data.popitem(last=False)


_inline_cache = TTLCache(maxsize=128, ttl=15)  # экспортируем в main


SYSTEM_PROMPT_PATH = PROJECT_ROOT / "system_prompt.txt"


def generate_punch(client: OpenAI) -> str:
    """Вызывает LLM, фильтрует сравнения (как/будто/словно) и возвращает уже санитизированный панч."""
    try:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_prompt = f.read().strip()
    except Exception as e:
        logger.warning(f"Failed to load system prompt from file: {e}. Using default.")
        system_prompt = (
            "Ты — Oxxxymiron, легендарный рэпер и мастер нелепых панчлайнов.\n"
            "Создавай короткие, метафоричные, нелепые, порой абсурдные и смешные панчи (1–4 строки максимум).\n"
            "Ответ — только сам панч, без комментариев. "
            "В конце добавь '\\n\\n<i>©oxxxymiron</i>'."
        )

    max_generation_attempts = 5
    last_raw = ""

    for attempt in range(max_generation_attempts):
        examples = sample_examples(20)
        user_prompt = f"Примеры:\n\n{examples}\n\nТеперь придумай новый панч."
        try:
            r = client.chat.completions.create(
                model=LLM_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.85,
                max_tokens=96,
                presence_penalty=0.5,
                frequency_penalty=0.5,
            )
            raw = (r.choices[0].message.content or "").strip().replace("\u00A0", " ")
            last_raw = raw

            # Проверяем, содержит ли сгенерированный панч слова-сравнения
            if not re.search(r"\b(как|будто|словно)\b", raw.lower()):
                return sanitize_punch(raw)
            else:
                logger.info(f"Generated punch rejected due to comparison word: '{raw}'. Retrying...")
        except (RateLimitError, APIConnectionError, APIStatusError) as e:
            logger.warning(f"LLM API call failed (attempt {attempt+1}/{max_generation_attempts}): {e}")
            if attempt == max_generation_attempts - 1:
                raise
            time.sleep(0.5 * (attempt + 1))

    logger.warning("All attempts generated comparison words, returning fallback.")
    return sanitize_punch(last_raw)