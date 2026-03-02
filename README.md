# @SveklovBot — Telegram ИИ-ассистент

Telegram-бот с ИИ на базе **Perplexity Sonar** — отвечает на вопросы с актуальной информацией из интернета.

## Возможности

- 💬 Личные сообщения — просто напиши вопрос боту
- 👥 Групповые чаты — упомяни `@SveklovBot`
- ⚡ Инлайн-режим — `@SveklovBot твой вопрос` в любом чате
- 🌐 Актуальные данные — Perplexity Sonar ищет информацию в интернете

## Стек

- **Python 3.12** + **aiogram 3**
- **Perplexity API** (модель `sonar` — самая дешёвая)
- Docker / Docker Compose

## Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/Svekloff/sveklov-bot.git
cd sveklov-bot
```

### 2. Настройка

```bash
cp .env.example .env
```

Заполните `.env`:

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `PERPLEXITY_API_KEY` | API-ключ Perplexity (`pplx-...`) |
| `BOT_USERNAME` | Имя бота без `@` |

### 3. Запуск через Docker

```bash
docker compose up -d --build
```

### 4. Логи

```bash
docker compose logs -f
```

## Настройка BotFather

1. Включите **Inline Mode**: `/mybots` → ваш бот → Bot Settings → Inline Mode → Enable
2. Отключите **Group Privacy**: `/mybots` → Bot Settings → Group Privacy → Disable

## Perplexity API

- Получить ключ: [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)
- Модель `sonar` — самая дешёвая ($1/M токенов вход / $1/M токенов выход)
- Документация: [docs.perplexity.ai](https://docs.perplexity.ai)

## Лицензия

MIT
