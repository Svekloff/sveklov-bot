# @SveklovBot — Telegram AI-бот на Google Gemini

AI-бот для Telegram, который отвечает на вопросы с актуальной информацией из интернета, используя [Google Gemini API](https://ai.google.dev) с Grounding through Google Search.

## Стоимость

**Бесплатно.** Free tier включает:
- Безлимит на генерацию токенов (15 RPM)
- 500 запросов с поиском Google в день

## Возможности

- **@mention в группах** — упомяните `@SveklovBot` с вопросом, бот ответит реплаем
- **Inline-режим** — наберите `@SveklovBot запрос` в любом чате
- **ЛС** — в личных сообщениях бот отвечает напрямую
- **Google Search** — автоматический поиск актуальной информации с источниками

## Быстрый старт

### 1. Получить токены

1. **Telegram Bot Token** — создайте бота через [@BotFather](https://t.me/BotFather):
   - `/newbot` → задайте имя и username → скопируйте токен
   - **Inline Mode:** `/mybots` → бот → `Bot Settings` → `Inline Mode` → `Turn on`
   - **Group Privacy:** `/mybots` → бот → `Bot Settings` → `Group Privacy` → `Turn off`

2. **Google Gemini API Key** — бесплатно на [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### 2. Настроить `.env`

```bash
cp .env.example .env
# Вставьте TELEGRAM_BOT_TOKEN и GEMINI_API_KEY
```

### 3. Запустить

#### Docker

```bash
docker compose up -d --build
```

#### Без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от BotFather | — |
| `GEMINI_API_KEY` | Ключ Google Gemini API | — |
| `GEMINI_MODEL` | Модель | `gemini-2.5-flash` |
| `SYSTEM_PROMPT` | Личность бота | см. `.env.example` |
| `MAX_TOKENS` | Макс. длина ответа | `1024` |
| `BOT_USERNAME` | Username бота (без @) | `SveklovBot` |

## Лицензия

MIT
