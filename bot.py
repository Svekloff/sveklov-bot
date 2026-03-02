import asyncio
import logging
import traceback

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
    logger.info(f"[/start] chat_type={message.chat.type} user={message.from_user.id}")
    await message.answer(
        "Привет! \U0001f44b\n\n"
        "Я — ИИ-помощник с доступом к интернету.\n\n"
        "• Напиши мне любой вопрос в личку\n"
        "• Упомяни @" + BOT_USERNAME + " в группе\n"
        "• Используй инлайн-режим: @" + BOT_USERNAME + " твой вопрос"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    logger.info(f"[/help] chat_type={message.chat.type} user={message.from_user.id}")
    await message.answer(
        "Как пользоваться:\n\n"
        "1. Личное сообщение — просто напиши вопрос\n"
        "2. Группа — упомяни @" + BOT_USERNAME + "\n"
        "3. Инлайн — в любом чате набери @" + BOT_USERNAME + " и вопрос"
    )


# ---------- Все текстовые сообщения (личка + группы) ----------

@dp.message(F.text)
async def handle_message(message: types.Message):
    logger.info(
        f"[сообщение] chat_type={message.chat.type} "
        f"user={message.from_user.id} text={message.text[:50]!r}"
    )

    is_private = message.chat.type == "private"
    is_group = message.chat.type in ("group", "supergroup")

    if is_group:
        bot_tag = f"@{BOT_USERNAME}"
        if bot_tag.lower() not in message.text.lower():
            return
        question = message.text.replace(bot_tag, "").replace(bot_tag.lower(), "").strip()
        if not question:
            await message.reply("Задай вопрос после упоминания.")
            return
    elif is_private:
        question = message.text
    else:
        return

    try:
        await bot.send_chat_action(message.chat.id, "typing")
        logger.info(f"[запрос Perplexity] question={question[:80]!r}")
        answer = await ask_perplexity(question)
        logger.info(f"[ответ Perplexity] len={len(answer)} answer={answer[:100]!r}")
    except Exception as e:
        logger.error(f"[ошибка Perplexity] {e}")
        answer = f"Ошибка при запросе: {e}"

    # Отправка без Markdown — чистый текст
    try:
        if is_group:
            await message.reply(answer[:4096], parse_mode=None)
        else:
            await message.answer(answer[:4096], parse_mode=None)
        logger.info("[отправка] OK")
    except Exception as e:
        logger.error(f"[отправка] FAILED: {e}")
        logger.error(traceback.format_exc())


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
    logger.info(f"Бот запущен. BOT_USERNAME={BOT_USERNAME}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
