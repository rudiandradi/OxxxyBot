# 🎤 OxxxyBot — Панчер XXI века

> *"Я не бот — я рифмую, пока ты дебажишь."*  
> — <i>©oxxxymiron</i>

---

## 💡 Что это

**OxxxyBot** — Telegram-бот, который генерирует панчлайны в духе **Oxxxymiron**.  
Он совмещает архивные фразы из `phrases.txt` и свежие, сгенерированные моделью **Groq LLM**.  
Каждый ответ стилизован под фирменный стиль с подписью:
> ©oxxxymiron

Бот написан на **Python 3.13** и использует:
- 🧠 `python-telegram-bot` v21  
- 🤖 `OpenAI` / `Groq API`  
- ⚙️ `python-dotenv`  
- 🧹 собственный санитайзер для чистого форматирования

---

## ⚙️ Установка и запуск

#### Установка
```bash
git clone https://github.com/<твой_ник>/OxxxyBot.git
cd OxxxyBot

uv pip install "python-telegram-bot>=21,<22" openai python-dotenv
```

#### Создай .env в корне
```bash
BOT_TOKEN=твой_токен_бота
GROQ_API_KEY=твой_api_ключ
LLM_URL=https://api.groq.com/openai/v1
LLM_NAME=llama-3.1-8b-instant
```

#### Запуск
```bash
uv run -m src.app.main
```

## Архитектура
<pre>
src/
├── app/
│   ├── main.py          # Telegram-бот и InlineQueryHandler
│   ├── groq_client.py   # Генерация панчей через Groq API
│   ├── phrases.py       # Работа с локальными панчами (phrases.txt)
│   └── text_utils.py    # Очистка, форматирование и подпись ©oxxxymiron
└── core/
    └── config.py        # Настройки и ключи из .env
</pre>
