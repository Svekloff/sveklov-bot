import asyncio
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from config import TELEGRAM_BOT_TOKEN, BOT_USERNAME
from perplexity_client import ask_perplexity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


# ---------- Команды ----------

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! 👋\n\n"
        "Я — ИИ-помощник с доступом к интернету.\n\n"
        "• Напиши мне любой вопрос в личку\n"
        "• Упомяни @" + BOT_USERNAME + " в группе\n"
        "• Используй инлайн-режим: @" + BOT_USERNAME + " твой вопрос"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 Как пользоваться:\n\n"
        "1️⃣ Личное сообщение — просто напиши вопрос\n"
        "2️⃣ Группа — упомяни @" + BOT_USERNAME + "\n"
        "3️⃣ Инлайн — в любом чате набери @" + BOT_USERNAME + " и вопрос"
    )


# ---------- Личные сообщения ----------

@dp.message(F.chat.type == "private")
async def handle_private(message: types.Message):
    if not message.text:
        return
    await bot.send_chat_action(message.chat.id, "typing")
    answer = await ask_perplexity(message.text)
    await message.answer(answer, parse_mode="Markdown")


# ---------- Упоминание в группе ----------

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group(message: types.Message):
    if not message.text:
        return

    bot_tag = f"@{BOT_USERNAME}"
    if bot_tag.lower() not in message.text.lower():
        return

    question = message.text.replace(bot_tag, "").replace(bot_tag.lower(), "").strip()
    if not question:
        await message.reply("Задай вопрос после упоминания.")
        return

    await bot.send_chat_action(message.chat.id, "typing")
    answer = await ask_perplexity(question)
    await message.reply(answer, parse_mode="Markdown")


# ---------- Инлайн-режим ----------

@dp.inline_query()
async def handle_inline(inline_query: InlineQuery):
    query_text = inline_query.query.strip()
    if not query_text:
        return

    answer = await ask_perplexity(query_text)
    short_answer = answer[:200] + "…" if len(answer) > 200 else answer

    result = InlineQueryResultArticle(
        id="1",
        title=f"Ответ на: {query_text[:50]}",
        description=short_answer,
        input_message_content=InputTextMessageContent(
            message_text=answer[:4096],
            parse_mode="Markdown",
        ),
    )
    await inline_query.answer([result], cache_time=30)


# ---------- Запуск ----------

async def main():
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
