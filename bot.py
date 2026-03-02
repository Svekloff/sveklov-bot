import asyncio
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from aiogram.enums import ParseMode

from config import TELEGRAM_BOT_TOKEN, BOT_USERNAME
from perplexity_client import ask_perplexity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


async def safe_reply(message: types.Message, text: str, **kwargs):
    """Отправляет ответ, пробуя сначала Markdown, потом plain text."""
    try:
        await message.answer(text, parse_mode=ParseMode.MARKDOWN, **kwargs)
    except Exception:
        try:
            await message.answer(text, parse_mode=None, **kwargs)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение: {e}")
            await message.answer("Произошла ошибка при отправке ответа.", parse_mode=None)


async def safe_reply_to(message: types.Message, text: str, **kwargs):
    """Отправляет reply, пробуя сначала Markdown, потом plain text."""
    try:
        await message.reply(text, parse_mode=ParseMode.MARKDOWN, **kwargs)
    except Exception:
        try:
            await message.reply(text, parse_mode=None, **kwargs)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение: {e}")
            await message.reply("Произошла ошибка при отправке ответа.", parse_mode=None)


# ---------- Команды ----------

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! \U0001f44b\n\n"
        "Я — ИИ-помощник с доступом к интернету.\n\n"
        "• Напиши мне любой вопрос в личку\n"
        "• Упомяни @" + BOT_USERNAME + " в группе\n"
        "• Используй инлайн-режим: @" + BOT_USERNAME + " твой вопрос"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "\U0001f4d6 Как пользоваться:\n\n"
        "1\ufe0f\u20e3 Личное сообщение — просто напиши вопрос\n"
        "2\ufe0f\u20e3 Группа — упомяни @" + BOT_USERNAME + "\n"
        "3\ufe0f\u20e3 Инлайн — в любом чате набери @" + BOT_USERNAME + " и вопрос"
    )


# ---------- Личные сообщения ----------

@dp.message(F.chat.type == "private")
async def handle_private(message: types.Message):
    if not message.text:
        return
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        answer = await ask_perplexity(message.text)
        await safe_reply(message, answer)
    except Exception as e:
        logger.error(f"Ошибка в handle_private: {e}")
        await message.answer(f"Ошибка: {e}", parse_mode=None)


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

    try:
        await bot.send_chat_action(message.chat.id, "typing")
        answer = await ask_perplexity(question)
        await safe_reply_to(message, answer)
    except Exception as e:
        logger.error(f"Ошибка в handle_group: {e}")
        await message.reply(f"Ошибка: {e}", parse_mode=None)


# ---------- Инлайн-режим ----------

@dp.inline_query()
async def handle_inline(inline_query: InlineQuery):
    query_text = inline_query.query.strip()
    if not query_text:
        return

    try:
        answer = await ask_perplexity(query_text)
        short_answer = answer[:200] + "…" if len(answer) > 200 else answer

        result = InlineQueryResultArticle(
            id="1",
            title=f"Ответ на: {query_text[:50]}",
            description=short_answer,
            input_message_content=InputTextMessageContent(
                message_text=answer[:4096],
            ),
        )
        await inline_query.answer([result], cache_time=30)
    except Exception as e:
        logger.error(f"Ошибка в handle_inline: {e}")
        result = InlineQueryResultArticle(
            id="1",
            title="Ошибка",
            description=str(e)[:100],
            input_message_content=InputTextMessageContent(
                message_text=f"Ошибка: {e}",
            ),
        )
        await inline_query.answer([result], cache_time=5)


# ---------- Запуск ----------

async def main():
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
