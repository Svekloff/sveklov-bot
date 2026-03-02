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

from config import TELEGRAM_BOT_TOKEN, BOT_USERNAME, BUSINESS_SYSTEM_PROMPT
from perplexity_client import ask_perplexity
from speech_to_text import transcribe_voice

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


# ---------- Бизнес-сообщения (ответ от имени Алексея) ----------

@dp.business_message()
async def handle_business_message(message: types.Message):
    """Обрабатывает сообщения от клиентов в бизнес-чатах (текст + голос)."""
    conn_id = message.business_connection_id
    if not conn_id:
        return

    # Определяем текст: из текстового или голосового сообщения
    if message.voice:
        logger.info(
            f"[бизнес голос] chat_id={message.chat.id} "
            f"user={message.from_user.id} conn_id={conn_id} "
            f"duration={message.voice.duration}s"
        )
        try:
            await bot.send_chat_action(
                chat_id=message.chat.id,
                action="typing",
                business_connection_id=conn_id,
            )
            question = await _transcribe_voice(message)
            if not question:
                return
        except Exception as e:
            logger.error(f"[бизнес голос ошибка] {e}")
            logger.error(traceback.format_exc())
            return
    elif message.text:
        question = message.text
    else:
        return

    logger.info(
        f"[бизнес сообщение] chat_id={message.chat.id} "
        f"user={message.from_user.id} conn_id={conn_id} "
        f"text={question[:50]!r}"
    )

    try:
        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing",
            business_connection_id=conn_id,
        )

        # Используем бизнес-промпт: бот отвечает как Алексей
        answer = await ask_perplexity(
            question,
            system_prompt=BUSINESS_SYSTEM_PROMPT,
        )
        logger.info(f"[бизнес ответ] len={len(answer)} text={answer[:80]!r}")

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


# ---------- Голосовые сообщения (личка бота) ----------

async def _transcribe_voice(message: types.Message) -> str | None:
    """Скачивает голосовое сообщение и транскрибирует через Groq Whisper."""
    voice = message.voice
    file = await bot.get_file(voice.file_id)
    file_data = await bot.download_file(file.file_path)

    # file_data — BytesIO объект
    audio_bytes = file_data.read()
    logger.info(f"[голос] скачано {len(audio_bytes)} байт, duration={voice.duration}s")

    text = await transcribe_voice(audio_bytes)
    if not text:
        logger.warning("[голос] пустая транскрипция")
        return None

    logger.info(f"[голос транскрипция] {text[:100]!r}")
    return text


@dp.message(F.voice)
async def handle_voice(message: types.Message):
    """Обрабатывает голосовые сообщения в личке бота."""
    if message.chat.type != "private":
        return

    logger.info(
        f"[голос] chat_id={message.chat.id} user={message.from_user.id} "
        f"duration={message.voice.duration}s"
    )

    try:
        await bot.send_chat_action(message.chat.id, "typing")
        question = await _transcribe_voice(message)
        if not question:
            await message.reply("Не удалось распознать голосовое сообщение.")
            return

        await bot.send_chat_action(message.chat.id, "typing")
        answer = await ask_perplexity(question)
        logger.info(f"[голос ответ] len={len(answer)}")
        result = await bot.send_message(
            chat_id=message.chat.id,
            text=answer[:4096],
            reply_to_message_id=message.message_id,
        )
        logger.info(f"[голос отправка OK] message_id={result.message_id}")
    except Exception as e:
        logger.error(f"[голос ошибка] {e}")
        logger.error(traceback.format_exc())


# ---------- Обычные сообщения (личка бота + группы) ----------

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
