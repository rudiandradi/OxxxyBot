import logging
import asyncio
import time
import random
from uuid import uuid4
from collections import defaultdict

from telegram import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
    constants,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.helpers import mention_html
from telegram.ext import (
    ApplicationBuilder,
    InlineQueryHandler,
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
)

from src.core.config import BOT_TOKEN
from src.app.phrases import reload_phrases, return_punch
from src.app.groq_client import get_client, generate_punch, _inline_cache
from src.app.text_utils import strip_signature


# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === ГЛОБАЛЬНЫЕ ДАННЫЕ ===
initial_punches = reload_phrases()
ROUNDS: dict[tuple[int, int], dict] = {}
SCORES: defaultdict[tuple[int, int], int] = defaultdict(int)
NAMES: dict[tuple[int, int], str] = {}


# === INLINE РЕЖИМ ===
def _cache_key(user_id: int, query_text: str) -> tuple:
    if not query_text:
        bucket = int(time.time() / 2)
        return (user_id, "<empty>", bucket)
    return (user_id, query_text)


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
        input_message_content=InputTextMessageContent(
            generated, parse_mode=constants.ParseMode.HTML
        ),
    )

    await update.inline_query.answer([local_result, ai_result], cache_time=3, is_personal=True)


# === ИГРА ===
def _make_game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Oxxxymiron", callback_data="guess:real"),
            InlineKeyboardButton("AI", callback_data="guess:ai"),
        ],
        [InlineKeyboardButton("Ещё раунд 🔁", callback_data="again")],
    ])


async def _new_round_text(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, str]:
    if random.random() < 0.5:
        global initial_punches
        punch, _ = return_punch(initial_punches)
        text = strip_signature(punch)
        label = "real"
    else:
        client = get_client()
        gen = await asyncio.to_thread(generate_punch, client)
        text = strip_signature(gen)
        label = "ai"

    if not text.strip():
        text = "…"
    return text, label


def _update_name_cache(user, chat_id: int):
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    name = name.strip() or (user.username and f"@{user.username}") or str(user.id)
    NAMES[(chat_id, user.id)] = name


def _format_scoreboard(chat_id: int) -> str:
    """Формирует топ-таблицу текущего чата."""
    players = [(uid, score, NAMES.get((chat_id, uid), str(uid)))
               for (cid, uid), score in SCORES.items() if cid == chat_id]
    if not players:
        return "Пока никто не играл 😅"

    players.sort(key=lambda x: x[1], reverse=True)
    lines = []
    for idx, (uid, score, name) in enumerate(players, start=1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        lines.append(f"{medal} {name}: <b>{score}</b>")
    return "🏆 <b>Рейтинг игроков</b>\n" + "\n".join(lines)


async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, label = await _new_round_text(context)
    msg = await update.message.reply_text(
        f"Настоящий ли панч?\n\n{text}",
        reply_markup=_make_game_keyboard(),
        parse_mode=constants.ParseMode.HTML,
    )
    ROUNDS[(msg.chat_id, msg.message_id)] = {"answer": label}


async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    chat_id = q.message.chat_id
    message_id = q.message.message_id
    data = q.data or ""

    if data == "again":
        text, label = await _new_round_text(context)
        ROUNDS[(chat_id, message_id)] = {"answer": label}
        await q.edit_message_text(
            f"Настоящий ли панч?\n\n{text}",
            reply_markup=_make_game_keyboard(),
            parse_mode=constants.ParseMode.HTML,
        )
        return

    if not data.startswith("guess:"):
        return

    round_data = ROUNDS.get((chat_id, message_id))
    if not round_data:
        await q.edit_message_text(
            "Раунд устарел 😔 Нажми «Ещё раунд 🔁», чтобы продолжить.",
            parse_mode=constants.ParseMode.HTML,
        )
        return

    correct = round_data["answer"]
    user = q.from_user
    _update_name_cache(user, chat_id)

    who = mention_html(user.id, user.first_name or "Игрок")
    user_choice = data.split(":", 1)[1]
    is_correct = user_choice == correct

    if is_correct:
        SCORES[(chat_id, user.id)] += 1
        verdict = "✅ Верно!"
    else:
        verdict = "❌ Не верно!"

    total = SCORES[(chat_id, user.id)]
    name = NAMES.get((chat_id, user.id), user.first_name or "Игрок")

    scoreboard = _format_scoreboard(chat_id)
    ROUNDS.pop((chat_id, message_id), None)

    await q.edit_message_text(
        f"{who}: {verdict}\n"
        f"<b>Очки {name}:</b> {total}\n\n"
        f"{scoreboard}\n\n"
        f"Хочешь сыграть ещё?",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Ещё раунд 🔁", callback_data="again")]]
        ),
        parse_mode=constants.ParseMode.HTML,
    )


# === ОБРАБОТКА ОШИБОК И ЗАПУСК ===
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(InlineQueryHandler(inlinequery))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CallbackQueryHandler(game_callback))
    app.add_error_handler(on_error)

    logger.info("Bot started. Waiting for inline queries and /game…")
    app.run_polling()


if __name__ == "__main__":
    main()