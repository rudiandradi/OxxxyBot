import asyncio
import logging
from uuid import uuid4

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update, constants
from telegram.ext import ApplicationBuilder, InlineQueryHandler, ContextTypes

from src.core.config import BOT_TOKEN
from src.app.phrases import reload_phrases, return_punch
from src.app.groq_client import get_client, generate_punch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

initial_punches = reload_phrases()

async def inlinequery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global initial_punches
    punch, initial_punches = return_punch(initial_punches)

    local_result = InlineQueryResultArticle(
        id=str(uuid4()),
        title="ВЫДАТЬ ПАНЧ",
        input_message_content=InputTextMessageContent(
            punch, parse_mode=constants.ParseMode.HTML
        ),
    )

    client = get_client()
    generated = await asyncio.to_thread(generate_punch, client)
    ai_result = InlineQueryResultArticle(
        id=str(uuid4()),
        title="СГЕНЕРИРОВАТЬ ПАНЧ",
        input_message_content=InputTextMessageContent(
            generated, parse_mode=constants.ParseMode.HTML
        ),
    )

    await update.inline_query.answer([local_result, ai_result], cache_time=0, is_personal=True)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(InlineQueryHandler(inlinequery))
    logger.info("Bot started. Waiting for inline queries…")
    app.run_polling()

if __name__ == "__main__":
    main()