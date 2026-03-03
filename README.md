# sveklov-bot

AI-powered Telegram bot built with aiogram 3 + Perplexity API.

## Features

- 💬 Private chat with conversation history
- 🏢 Business account auto-reply mode
- 👥 Group chat support (mention bot to trigger)
- 🎤 Voice message transcription (Whisper)
- 🖼 Image analysis
- 🔍 Inline query mode
- 📋 Group management via bot UI with inline keyboard

## Setup

```bash
cp .env.example .env
# Fill in your tokens
pip install -r requirements.txt
python bot.py
```

## Commands

- `/start` — Welcome message
- `/groups` — Manage active groups (owner only)

## Docker

```bash
docker-compose up -d
```
