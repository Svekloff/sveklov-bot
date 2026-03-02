# @SveklovBot — Telegram AI-бот на Perplexity Sonar

AI-бот для Telegram, который отвечает на вопросы с актуальной информацией из интернета, используя [Perplexity Sonar API](https://docs.perplexity.ai).

## Возможности

- **@mention в группах** — упомяните `@SveklovBot` с вопросом, бот ответит реплаем
- **Inline-режим** — наберите `@SveklovBot запрос` в любом чате для быстрого поиска
- **ЛС** — в личных сообщениях бот отвечает на все вопросы напрямую
- **Веб-поиск** — Perplexity Sonar автоматически ищет актуальную информацию и добавляет источники

## Быстрый старт

### 1. Получить токены

1. **Telegram Bot Token** — создайте бота через [@BotFather](https://t.me/BotFather):
   - Отправьте `/newbot`, задайте имя и username
   - Скопируйте токен
   - **Включите inline-режим:** `/mybots` → выберите бота → `Bot Settings` → `Inline Mode` → `Turn on`
   - **Выключите Privacy Mode** (для чтения сообщений в группах): `/mybots` → бот → `Bot Settings` → `Group Privacy` → `Turn off`

2. **Perplexity API Key** — получите на [docs.perplexity.ai](https://docs.perplexity.ai) в разделе API Keys

### 2. Настроить `.env`

```bash
cp .env.example .env
# Отредактируйте .env — вставьте свои токены
```

### 3. Запустить

#### Docker (рекомендуется)

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

## Структура проекта

```
sveklov-bot/
├── bot.py               # Основной файл — обработчики Telegram
├── perplexity_client.py # Клиент для Perplexity Sonar API
├── config.py            # Конфигурация из переменных окружения
├── requirements.txt     # Python-зависимости
├── Dockerfile           # Docker-образ
├── docker-compose.yml   # Docker Compose для запуска
├── .env.example         # Шаблон переменных окружения
├── .dockerignore
├── .gitignore
└── README.md
```

## Настройка в BotFather

Не забудьте:
1. `/mybots` → бот → `Bot Settings` → **Inline Mode** → `Turn on`
2. `/mybots` → бот → `Bot Settings` → **Group Privacy** → `Turn off`

Без этого inline-запросы и ответы в группах работать не будут.

## Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от BotFather | — |
| `PERPLEXITY_API_KEY` | Ключ API Perplexity | — |
| `PERPLEXITY_MODEL` | Модель Sonar | `sonar-pro` |
| `SYSTEM_PROMPT` | Системный промпт для бота | см. `.env.example` |
| `MAX_TOKENS` | Макс. длина ответа | `1024` |
| `BOT_USERNAME` | Username бота (без @) | `SveklovBot` |

## Стоимость

Perplexity Sonar API тарифицируется по токенам. Модель `sonar-pro` стоит дороже `sonar`, но даёт более качественные ответы с поиском. Следите за расходами в [API Portal](https://docs.perplexity.ai).

## Лицензия

MIT
