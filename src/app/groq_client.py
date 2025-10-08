import logging
from openai import OpenAI
from src.app.text_utils import sanitize_punch
from src.core.config import GROQ_API_KEY, LLM_URL, LLM_NAME
from src.app.phrases import reload_phrases

logger = logging.getLogger(__name__)

def get_client() -> OpenAI:
    logger.info(f"Connecting to Groq model {LLM_NAME}…")
    return OpenAI(api_key=GROQ_API_KEY, base_url=LLM_URL)

def generate_punch(client: OpenAI) -> str:
    examples = "\n".join(reload_phrases()[:10])
    system_prompt = (
        "Ты — Oxxxymiron, легендарный рэпер и мастер нелепых панчлайнов.\n"
        "Создавай короткие, метафоричные, остроумные панчи (1–4 строки максимум).\n"
        "Ответ — только сам панч, без комментариев. "
        "В конце добавь '\\n\\n<i>©oxxxymiron</i>'."
    )
    user_prompt = f"Вот примеры:\n\n{examples}\n\nТеперь придумай новый панч."

    r = client.chat.completions.create(
        model=LLM_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
        max_tokens=150,
    )
    raw = (r.choices[0].message.content or "").strip().replace("\u00A0", " ")
    return sanitize_punch(raw)