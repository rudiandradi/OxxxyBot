import logging
import time
from collections import OrderedDict
from openai import OpenAI
from openai import APIConnectionError, RateLimitError, APIStatusError

from src.core.config import GROQ_API_KEY, LLM_URL, LLM_NAME
from src.app.text_utils import sanitize_punch
from src.app.phrases import sample_examples

logger = logging.getLogger(__name__)


def get_client() -> OpenAI:
    """Создаёт клиента Groq с общим HTTP-дедлайном."""
    logger.info(f"Connecting to Groq model {LLM_NAME}…")
    return OpenAI(api_key=GROQ_API_KEY, base_url=LLM_URL, timeout=15.0)


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
EXAMPLES_FOR_PROMPT = sample_examples(20)


def generate_punch(client: OpenAI) -> str:
    """Вызывает LLM и возвращает уже санитизированный панч."""
    examples = EXAMPLES_FOR_PROMPT
    system_prompt = (
        "Ты — Oxxxymiron, легендарный рэпер и мастер нелепых панчлайнов.\n"
        "Создавай короткие, метафоричные, нелепые, порой абсурдные и смешные панчи (1–4 строки максимум).\n"
        "Ответ — только сам панч, без комментариев. "
        "В конце добавь '\\n\\n<i>©oxxxymiron</i>'."
    )
    user_prompt = f"Примеры:\n\n{examples}\n\nТеперь придумай новый панч."

    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=LLM_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.6,
                max_tokens=96,
                presence_penalty=0.2,
                frequency_penalty=0.4,
            )
            raw = (r.choices[0].message.content or "").strip().replace("\u00A0", " ")
            return sanitize_punch(raw)
        except (RateLimitError, APIConnectionError, APIStatusError) as e:
            logger.warning(f"LLM call failed (attempt {attempt+1}/3): {e}")
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))