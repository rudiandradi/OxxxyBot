import logging
import asyncio
import time
from uuid import uuid4

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update, constants
from telegram.ext import ApplicationBuilder, InlineQueryHandler, ContextTypes

from src.core.config import BOT_TOKEN
from src.app.phrases import reload_phrases, return_punch
from src.app.groq_client import get_client, generate_punch, _inline_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

initial_punches = reload_phrases()


def _cache_key(user_id: int, query_text: str) -> tuple:
    """
    Ключ кэша:
      - если запрос пустой -> time-bucket 2s, чтобы результат обновлялся каждые ~2 секунды
      - если непустой -> классический ключ (жёсткий кэш на 15s внутри TTLCache)
    """
    if not query_text:
        bucket = int(time.time() / 2)  # новый ключ каждые 2 секунды
        return (user_id, "<empty>", bucket)
    return (user_id, query_text)


async def inlinequery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Два inline-результата: локальный и генеративный (LLM с «умным» кэшем)."""
    global initial_punches
    punch, initial_punches = return_punch(initial_punches)

    # 1) Реальный панч
    local_result = InlineQueryResultArticle(
        id=str(uuid4()),
        title="ВЫДАТЬ ПАНЧ",
        description="РЕАЛЬНЫЙ ПАНЧ ЯНЫЧА",
        input_message_content=InputTextMessageContent(
            punch, parse_mode=constants.ParseMode.HTML
        ),
    )

    # 2) Генеративный панч
    query_text = (update.inline_query.query or "").strip()
    key = _cache_key(update.inline_query.from_user.id, query_text)
    cached = _inline_cache.get(key)

    if cached is None:
        try:
            client = get_client()
            generated = await asyncio.to_thread(generate_punch, client)
            _inline_cache.set(key, generated)
        except Exception as e:
            logger.warning(f"LLM error: {e}")
            generated = "Сеть зависла — держи архивный панч.\n\n<i>©oxxxymiron</i>"
    else:
        generated = cached

    ai_result = InlineQueryResultArticle(
        id=str(uuid4()),
        title="СГЕНЕРИРОВАТЬ ПАНЧ",
        description="ВЫДУМАННЫЙ НЕЛЕПЫЙ ПАНЧ МИРОНА",
        input_message_content=InputTextMessageContent(
            generated, parse_mode=constants.ParseMode.HTML
        ),
    )

    await update.inline_query.answer([local_result, ai_result], cache_time=3, is_personal=True)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(InlineQueryHandler(inlinequery))
    app.add_error_handler(on_error)
    logger.info("Bot started. Waiting for inline queries…")
    app.run_polling()


if __name__ == "__main__":
    main()