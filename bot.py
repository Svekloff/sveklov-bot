import asyncio
import logging
import traceback

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    BusinessConnection,
)

from config import TELEGRAM_BOT_TOKEN, BOT_USERNAME
from perplexity_client import ask_perplexity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Хранилище бизнес-подключений: {user_id: connection_id}
business_connections: dict[int, str] = {}


# ---------- Бизнес-подключение ----------

@dp.business_connection()
async def handle_business_connection(update: BusinessConnection):
    """Срабатывает, когда пользователь подключает/отключает бота как бизнес-бота."""
    user = update.user
    conn_id = update.id
    is_enabled = update.is_enabled
    can_reply = update.can_reply

    logger.info(
        f"[бизнес] Подключение: user={user.id} ({user.first_name}) "
        f"connection_id={conn_id} enabled={is_enabled} can_reply={can_reply}"
    )

    if is_enabled and can_reply:
        business_connections[user.id] = conn_id
        logger.info(f"[бизнес] Сохранён connection_id={conn_id} для user={user.id}")
    else:
        business_connections.pop(user.id, None)
        logger.info(f"[бизнес] Удалён connection_id для user={user.id}")


# ---------- Бизнес-сообщения (ответ от имени владельца) ----------

@dp.business_message()
async def handle_business_message(message: types.Message):
    """Обрабатывает сообщения от клиентов в бизнес-чатах."""
    if not message.text:
        return

    conn_id = message.business_connection_id
    if not conn_id:
        return

    logger.info(
        f"[бизнес сообщение] chat_id={message.chat.id} "
        f"user={message.from_user.id} conn_id={conn_id} "
        f"text={message.text[:50]!r}"
    )

    try:
        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing",
            business_connection_id=conn_id,
        )
        answer = await ask_perplexity(message.text)
        logger.info(f"[бизнес ответ] len={len(answer)}")

        result = await bot.send_message(
            chat_id=message.chat.id,
            text=answer[:4096],
            business_connection_id=conn_id,
        )
        logger.info(f"[бизнес отправка OK] message_id={result.message_id}")
    except Exception as e:
        logger.error(f"[бизнес ошибка] {e}")
        logger.error(traceback.format_exc())


# ---------- Команды ----------

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    logger.info(f"[/start] chat_id={message.chat.id} user={message.from_user.id}")
    await bot.send_message(
        chat_id=message.chat.id,
        text=(
            "Привет!\n\n"
            "Я — ИИ-помощник с доступом к интернету.\n\n"
            "• Напиши мне любой вопрос в личку\n"
            "• Упомяни @" + BOT_USERNAME + " в группе\n"
            "• Используй инлайн-режим: @" + BOT_USERNAME + " твой вопрос"
        ),
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Как пользоваться:\n\n"
        "1. Личное сообщение — просто напиши вопрос\n"
        "2. Группа — упомяни @" + BOT_USERNAME + "\n"
        "3. Инлайн — @" + BOT_USERNAME + " и вопрос"
    )


# ---------- Обычные сообщения (личка + группы) ----------

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
        answer = await ask_perplexity(question)
        logger.info(f"[ответ] len={len(answer)}")
        result = await bot.send_message(
            chat_id=message.chat.id,
            text=answer[:4096],
            reply_to_message_id=message.message_id if is_group else None,
        )
        logger.info(f"[отправка OK] message_id={result.message_id}")
    except Exception as e:
        logger.error(f"[ошибка] {e}")
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
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "edited_message",
            "inline_query",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
