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
from html import escape as escape_html
from telegram.ext import (
    ApplicationBuilder,
    InlineQueryHandler,
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
)

from src.core.config import BOT_TOKEN, BOT_NAME
from src.app.phrases import reload_phrases, return_punch
from src.app.llm_client import get_client, generate_punch, _inline_cache
from src.app.text_utils import strip_signature
from src.app.storage import (
    init_db, add_fav, list_favs, clear_favs,
    list_fav_rows, delete_fav
)

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === ГЛОБАЛЬНЫЕ ДАННЫЕ ===
initial_punches = reload_phrases()

# (chat_id, message_id) -> {"answer": "real"/"ai", "text": "<punch_text>"}
ROUNDS: dict[tuple[int, int], dict] = {}
SCORES: defaultdict[tuple[int, int], int] = defaultdict(int)
NAMES: dict[tuple[int, int], str] = {}
STATS: defaultdict[tuple[int, int], dict] = defaultdict(lambda: {"correct": 0, "wrong": 0})

# === INLINE ===
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

# === GAME ===
def _make_game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Oxxxymiron", callback_data="guess:real"),
            InlineKeyboardButton("AI", callback_data="guess:ai"),
        ],
        [
            InlineKeyboardButton("Цитировать", callback_data="quote"),
            InlineKeyboardButton("В избранное", callback_data="fav"),
        ],
    ])

def _make_after_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Ещё раунд 🔁", callback_data="again")]])

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
    players = []
    for (cid, uid), score in SCORES.items():
        if cid != chat_id:
            continue
        name = NAMES.get((chat_id, uid), str(uid))
        s = STATS.get((chat_id, uid), {"correct": 0, "wrong": 0})
        players.append((uid, score, name, s["correct"], s["wrong"]))
    if not players:
        return "Пока никто не играл"
    players.sort(key=lambda x: (-x[1], x[0]))
    lines = [f"{escape_html(name)}: <b>{score}</b> (✓ {ok} / ✗ {bad})"
             for (_, score, name, ok, bad) in players]
    return "<b>Рейтинг игроков</b>\n" + "\n".join(lines)

async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, label = await _new_round_text(context)
    msg = await update.message.reply_text(
        f"Настоящий ли панч?\n\n{text}",
        reply_markup=_make_game_keyboard(),
        parse_mode=constants.ParseMode.HTML,
        disable_web_page_preview=True,
    )
    ROUNDS[(msg.chat_id, msg.message_id)] = {"answer": label, "text": text}

async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query

    chat_id = q.message.chat_id
    message_id = q.message.message_id
    data = q.data or ""
    key = (chat_id, message_id)
    round_data = ROUNDS.get(key)

    if not round_data and data in ("quote", "fav"):
        await q.answer("Раунд устарел.", show_alert=False)
        return

    if data == "again":
        text, label = await _new_round_text(context)
        ROUNDS[key] = {"answer": label, "text": text}
        await q.answer()
        await q.edit_message_text(
            f"Настоящий ли панч?\n\n{text}",
            reply_markup=_make_game_keyboard(),
            parse_mode=constants.ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    if data == "quote":
        await q.answer()
        punch = round_data["text"]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{punch}",
            parse_mode=constants.ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    if data == "fav":
        punch = round_data["text"]
        ok = add_fav(q.from_user.id, punch)
        await q.answer("Добавлено в избранное" if ok else "Уже в избранном", show_alert=False)
        return

    # Обработка угадывания
    if not data.startswith("guess:"):
        await q.answer()
        return

    if not round_data:
        await q.answer()
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

    stats_key = (chat_id, user.id)
    if is_correct:
        SCORES[stats_key] += 1
        STATS[stats_key]["correct"] += 1
        verdict = "✅ Верно!"
    else:
        SCORES[stats_key] = 0
        STATS[stats_key]["wrong"] += 1
        verdict = "❌ Не верно!"

    total = SCORES[stats_key]
    ok = STATS[stats_key]["correct"]
    bad = STATS[stats_key]["wrong"]
    name = NAMES.get((chat_id, user.id), user.first_name or "Игрок")

    scoreboard = _format_scoreboard(chat_id)

    await q.answer()

    await q.edit_message_text(
        f"{who}: {verdict}\n"
        f"<b>Очки {escape_html(name)}:</b> {total}\n\n"
        f"{scoreboard}\n\n",
        reply_markup=_make_after_keyboard(),  # ← только "Ещё раунд"
        parse_mode=constants.ParseMode.HTML,
        disable_web_page_preview=True,
    )
    ROUNDS.pop(key, None)

# === FAVS / HELP ===
async def favs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покажет весь список с ID и инструкцией по точечному удалению."""
    user = update.effective_user
    display = user.first_name or (user.username and f"@{user.username}") or "Игрок"

    rows = list_fav_rows(user.id, limit=1_000_000)
    if not rows:
        await update.message.reply_text(
            f"У {escape_html(display)} пока нет избранных панчей. Нажми «В избранное» в игре.",
            parse_mode=constants.ParseMode.HTML,
            quote=True,
        )
        return

    header = f"Избранное {escape_html(display)} (всего {len(rows)}):\n" \
             f"Чтобы удалить конкретный пункт, используй команду: <code>/del_fav</code> ID\n\n"

    chunk = header
    for fav_id, text in rows:
        line = f"{fav_id}. {text}\n"
        if len(chunk) + len(line) > 3500:
            await update.message.reply_text(
                chunk, parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True
            )
            chunk = ""
        chunk += line
    if chunk:
        await update.message.reply_text(
            chunk, parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True
        )

async def del_fav_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить конкретный элемент: /del_fav 123"""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Использование: /del_fav <ID>\nПосмотри ID в /favs")
        return
    try:
        fav_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Пример: /del_fav 123")
        return

    ok = delete_fav(user.id, fav_id)
    if ok:
        await update.message.reply_text(f"Удалено из избранного: ID {fav_id}")
    else:
        await update.message.reply_text("Не найдено. Проверь ID (см. /favs)")

async def clear_favs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_favs(update.effective_user.id)
    await update.message.reply_text("Избранное очищено.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or (user.username and f"@{user.username}") or "Игрок"
    text = (
        f"<b>/game</b> — начать раунд. Угадай, панч настоящий или сгенерирован.\n"
        "Кнопка «В избранное» — добавляет панч в твой личный список.\n"
        "<b>/favs</b> — показать все твои избранные панчи с их ID.\n"
        "<b>/del_fav &lt;ID&gt;</b> — удалить один пункт из избранного по ID.\n"
        "<b>/clear_favs</b> — очистить список избранного полностью.\n"
        "ℹ<b>/help</b> — показать эту подсказку.\n\n"
        "Правила очков: за верный ответ +1, за неверный — счёт обнуляется. "
        "Рейтинг и статистика считаются отдельно для каждого чата.\n\n"
        f"Inline-режим: введи {escape_html(BOT_NAME)} в любом чате и выбери панч."
    )
    await update.message.reply_text(
        text, parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True
    )

# === ERRORS & RUN ===
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)

def main():
    init_db()

    # Фикс для версий Python 3.12+, где asyncio.get_event_loop() больше не создает цикл автоматически в основном потоке.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(InlineQueryHandler(inlinequery))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CallbackQueryHandler(game_callback))

    app.add_handler(CommandHandler("favs", favs_command))
    app.add_handler(CommandHandler("del_fav", del_fav_command))
    app.add_handler(CommandHandler("clear_favs", clear_favs_command))
    app.add_handler(CommandHandler("help", help_command))

    app.add_error_handler(on_error)

    logger.info("Bot started. Waiting for inline queries and /game…")
    app.run_polling()

if __name__ == "__main__":
    main()