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

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


# ---------- Команды ----------

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    logger.info(f"[/start] chat_id={message.chat.id} user={message.from_user.id}")
    result = await bot.send_message(
        chat_id=message.chat.id,
        text=(
            "Привет!\n\n"
            "Я — ИИ-помощник с доступом к интернету.\n\n"
            "• Напиши мне любой вопрос в личку\n"
            "• Упомяни @" + BOT_USERNAME + " в группе\n"
            "• Используй инлайн-режим: @" + BOT_USERNAME + " твой вопрос"
        ),
    )
    logger.info(f"[/start отправлен] message_id={result.message_id} chat_id={result.chat.id}")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Как пользоваться:\n\n"
        "1. Личное сообщение — просто напиши вопрос\n"
        "2. Группа — упомяни @" + BOT_USERNAME + "\n"
        "3. Инлайн — @" + BOT_USERNAME + " и вопрос"
    )


# ---------- Все текстовые сообщения ----------

@dp.message(F.text)
async def handle_message(message: types.Message):
    logger.info(
        f"[сообщение] chat_type={message.chat.type} "
        f"chat_id={message.chat.id} user={message.from_user.id} "
        f"text={message.text[:50]!r}"
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
        logger.info(f"[запрос] question={question[:80]!r}")
        answer = await ask_perplexity(question)
        logger.info(f"[ответ] len={len(answer)}")
    except Exception as e:
        logger.error(f"[ошибка API] {e}")
        answer = f"Ошибка: {e}"

    # Отправка напрямую через bot.send_message
    try:
        result = await bot.send_message(
            chat_id=message.chat.id,
            text=answer[:4096],
            reply_to_message_id=message.message_id if is_group else None,
        )
        logger.info(
            f"[отправка OK] message_id={result.message_id} "
            f"chat_id={result.chat.id} text_len={len(result.text)}"
        )
    except Exception as e:
        logger.error(f"[отправка FAILED] {e}")
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
        logger.error(f"[инлайн ошибка] {e}")


# ---------- Запуск ----------

async def main():
    logger.info(f"Бот запущен. BOT_USERNAME={BOT_USERNAME}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
