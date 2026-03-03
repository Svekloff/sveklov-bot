import asyncio
import logging
import traceback
from collections import defaultdict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    BusinessConnection,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ChatMemberUpdated,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    BOT_USERNAME,
    BUSINESS_SYSTEM_PROMPT,
    GROUP_SYSTEM_PROMPT,
    MAX_HISTORY,
    OWNER_ID,
)
from perplexity_client import ask_perplexity
from speech_to_text import transcribe_voice
from image_analyzer import analyze_image
import group_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Хранилище бизнес-подключений: {user_id: connection_id}
business_connections: dict[int, str] = {}

# Хранилище истории сообщений: {chat_id: [{role, content}, ...]}
chat_histories: dict[int, list[dict]] = defaultdict(list)


def _add_to_history(chat_id: int, role: str, content: str) -> None:
    chat_histories[chat_id].append({"role": role, "content": content})
    max_entries = MAX_HISTORY * 2
    if len(chat_histories[chat_id]) > max_entries:
        chat_histories[chat_id] = chat_histories[chat_id][-max_entries:]


def _get_history(chat_id: int) -> list[dict]:
    return list(chat_histories[chat_id])


def _is_owner(user_id: int) -> bool:
    """Проверяет, является ли пользователь владельцем бота."""
    return user_id == OWNER_ID


def _is_bot_mentioned(text: str) -> bool:
    if not text:
        return False
    bot_tag = f"@{BOT_USERNAME}"
    return bot_tag.lower() in text.lower()


def _strip_bot_mention(text: str) -> str:
    bot_tag = f"@{BOT_USERNAME}"
    result = text.replace(bot_tag, "").replace(bot_tag.lower(), "")
    return result.strip()


# ---------- Отслеживание групп ----------

@dp.my_chat_member()
async def handle_my_chat_member(update: ChatMemberUpdated):
    """Отслеживает добавление/удаление бота из групп."""
    chat = update.chat
    if chat.type not in ("group", "supergroup"):
        return

    new_status = update.new_chat_member.status
    old_status = update.old_chat_member.status

    if new_status in ("member", "administrator") and old_status in ("left", "kicked"):
        # Бот добавлен в группу
        group_manager.register_group(chat.id, chat.title or f"Группа {chat.id}")
        logger.info(f"[группы] бот добавлен в: {chat.id} ({chat.title})")
    elif new_status in ("left", "kicked") and old_status in ("member", "administrator"):
        # Бот удалён из группы
        group_manager.unregister_group(chat.id)
        logger.info(f"[группы] бот удалён из: {chat.id} ({chat.title})")


def _register_group_from_message(message: types.Message) -> None:
    """Регистрирует группу при получении любого сообщения из неё."""
    if message.chat.type in ("group", "supergroup"):
        title = message.chat.title or f"Группа {message.chat.id}"
        group_manager.register_group(message.chat.id, title)


# ---------- Меню управления группами ----------

def _build_groups_keyboard() -> InlineKeyboardMarkup:
    """Строит клавиатуру со списком всех известных групп и их статусом."""
    known = group_manager.get_known_groups()
    allowed = group_manager.get_allowed_ids()

    if not known:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Нет доступных групп",
                callback_data="groups_none"
            )]
        ])

    buttons = []
    for chat_id, title in sorted(known.items(), key=lambda x: x[1]):
        is_on = chat_id in allowed
        status = "✅" if is_on else "❌"
        short_title = title[:30] + "…" if len(title) > 30 else title
        buttons.append([InlineKeyboardButton(
            text=f"{status} {short_title}",
            callback_data=f"toggle_{chat_id}"
        )])

    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data="groups_refresh"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _groups_status_text() -> str:
    """Формирует текстовое описание статуса групп."""
    known = group_manager.get_known_groups()
    allowed = group_manager.get_allowed_ids()

    if not known:
        return (
            "Бот пока не добавлен ни в одну группу.\n\n"
            "Добавь меня в группу, и она появится здесь."
        )

    active = sum(1 for gid in known if gid in allowed)
    total = len(known)

    return (
        f"Управление группами ({active}/{total} активных)\n\n"
        "Нажми на группу, чтобы включить или выключить бота в ней."
    )


@dp.message(Command("groups"))
async def cmd_groups(message: types.Message):
    """Команда /groups — меню управления группами (только для владельца, только в личке)."""
    if not _is_owner(message.from_user.id):
        return

    if message.chat.type != "private":
        await message.reply("Эта команда работает только в личке бота.")
        return

    text = _groups_status_text()
    keyboard = _build_groups_keyboard()
    await message.answer(text, reply_markup=keyboard)


@dp.callback_query(F.data.startswith("toggle_"))
async def handle_toggle_group(callback: CallbackQuery):
    """Обработка нажатия на кнопку группы — включить/выключить."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    try:
        chat_id = int(callback.data.replace("toggle_", ""))
    except ValueError:
        await callback.answer("Ошибка")
        return

    new_state = group_manager.toggle_group(chat_id)
    known = group_manager.get_known_groups()
    group_name = known.get(chat_id, str(chat_id))

    if new_state:
        await callback.answer(f"Бот включён в «{group_name}»")
    else:
        await callback.answer(f"Бот выключен в «{group_name}»")

    # Обновляем сообщение с новой клавиатурой
    text = _groups_status_text()
    keyboard = _build_groups_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "groups_refresh")
async def handle_groups_refresh(callback: CallbackQuery):
    """Обновление списка групп."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    text = _groups_status_text()
    keyboard = _build_groups_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer("Обновлено")


@dp.callback_query(F.data == "groups_none")
async def handle_groups_none(callback: CallbackQuery):
    """Заглушка для пустого списка."""
    await callback.answer("Добавь бота в группу, и она появится здесь")


# ---------- Бизнес-подключение ----------

@dp.business_connection()
async def handle_business_connection(update: BusinessConnection):
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
    else:
        business_connections.pop(user.id, None)


# ---------- Бизнес-сообщения ----------

@dp.business_message()
async def handle_business_message(message: types.Message):
    conn_id = message.business_connection_id
    if not conn_id:
        return

    # Игнорируем исходящие сообщения (ответы бота от имени владельца)
    if message.from_user and message.from_user.id == OWNER_ID:
        return

    if message.voice:
        logger.info(
            f"[бизнес голос] chat_id={message.chat.id} "
            f"user={message.from_user.id} duration={message.voice.duration}s"
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
        f"text={question[:50]!r}"
    )

    try:
        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing",
            business_connection_id=conn_id,
        )

        history = _get_history(message.chat.id)
        answer = await ask_perplexity(
            question,
            system_prompt=BUSINESS_SYSTEM_PROMPT,
            history=history,
        )

        _add_to_history(message.chat.id, "user", question)
        _add_to_history(message.chat.id, "assistant", answer)

        await bot.send_message(
            chat_id=message.chat.id,
            text=answer[:4096],
            business_connection_id=conn_id,
        )
    except Exception as e:
        logger.error(f"[бизнес ошибка] {e}")
        logger.error(traceback.format_exc())


# ---------- Команды ----------

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    logger.info(f"[/start] chat_id={message.chat.id} user={message.from_user.id}")

    if _is_owner(message.from_user.id) and message.chat.type == "private":
        # Для владельца показываем расширенное меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Управление группами", callback_data="open_groups")]
        ])
        await bot.send_message(
            chat_id=message.chat.id,
            text=(
                "Привет!\n\n"
                "Я — ИИ-помощник с доступом к интернету.\n\n"
                "Напиши мне любой вопрос в личку, "
                "упомяни @" + BOT_USERNAME + " в группе "
                "или используй инлайн-режим.\n\n"
                "Команды управления:\n"
                "/groups — управление группами"
            ),
            reply_markup=keyboard,
        )
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text=(
                "Привет!\n\n"
                "Я — ИИ-помощник с доступом к интернету.\n\n"
                "Напиши мне любой вопрос в личку, "
                "упомяни @" + BOT_USERNAME + " в группе "
                "или используй инлайн-режим: @" + BOT_USERNAME + " твой вопрос"
            ),
        )


@dp.callback_query(F.data == "open_groups")
async def handle_open_groups(callback: CallbackQuery):
    """Открывает меню групп из кнопки в /start."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    text = _groups_status_text()
    keyboard = _build_groups_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "Как пользоваться:\n\n"
        "1. Личное сообщение — просто напиши вопрос\n"
        "2. Группа — упомяни @" + BOT_USERNAME + "\n"
        "3. Инлайн — @" + BOT_USERNAME + " и вопрос"
    )
    if _is_owner(message.from_user.id):
        text += "\n\nКоманды управления:\n/groups — управление группами"
    await message.answer(text)


@dp.message(Command("chatid"))
async def cmd_chatid(message: types.Message):
    await message.reply(f"Chat ID: {message.chat.id}")


# ---------- Голосовые сообщения ----------

async def _transcribe_voice(message: types.Message) -> str | None:
    voice = message.voice
    file = await bot.get_file(voice.file_id)
    file_data = await bot.download_file(file.file_path)

    audio_bytes = file_data.read()
    logger.info(f"[голос] скачано {len(audio_bytes)} байт, duration={voice.duration}s")

    text = await transcribe_voice(audio_bytes)
    if not text:
        logger.warning("[голос] пустая транскрипция")
        return None

    logger.info(f"[голос транскрипция] {text[:100]!r}")
    return text


async def _download_photo(message: types.Message) -> bytes | None:
    if not message.photo:
        return None
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_data = await bot.download_file(file.file_path)
    return file_data.read()


@dp.message(F.voice)
async def handle_voice(message: types.Message):
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
        await bot.send_message(
            chat_id=message.chat.id,
            text=answer[:4096],
            reply_to_message_id=message.message_id,
        )
    except Exception as e:
        logger.error(f"[голос ошибка] {e}")
        logger.error(traceback.format_exc())


# ---------- Фото ----------

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    is_group = message.chat.type in ("group", "supergroup")
    is_private = message.chat.type == "private"

    if is_group:
        _register_group_from_message(message)
        if not group_manager.is_group_allowed(message.chat.id):
            return
        caption = message.caption or ""
        if not _is_bot_mentioned(caption):
            return
        question = _strip_bot_mention(caption)
    elif is_private:
        question = message.caption or ""
    else:
        return

    logger.info(
        f"[фото] chat_type={message.chat.type} chat_id={message.chat.id} "
        f"user={message.from_user.id} caption={question[:50]!r}"
    )

    try:
        await bot.send_chat_action(message.chat.id, "typing")

        image_bytes = await _download_photo(message)
        if not image_bytes:
            return

        if is_group:
            sys_prompt = GROUP_SYSTEM_PROMPT
            vision_prompt = question if question else "Прокомментируй эту картинку/мем коротко и с юмором."
        else:
            sys_prompt = None
            vision_prompt = question if question else "Что на этой картинке?"

        history = _get_history(message.chat.id) if is_group else None
        answer = await analyze_image(
            image_bytes=image_bytes,
            prompt=vision_prompt,
            system_prompt=sys_prompt,
            history=history,
        )

        if not answer:
            return

        if is_group:
            user_desc = f"[картинка] {question}" if question else "[картинка]"
            _add_to_history(message.chat.id, "user", user_desc)
            _add_to_history(message.chat.id, "assistant", answer)

        await bot.send_message(
            chat_id=message.chat.id,
            text=answer[:4096],
            reply_to_message_id=message.message_id,
        )
    except Exception as e:
        logger.error(f"[фото ошибка] {e}")
        logger.error(traceback.format_exc())


# ---------- Текстовые сообщения ----------

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
        # Регистрируем группу при любом сообщении
        _register_group_from_message(message)

        # Проверяем белый список
        if not group_manager.is_group_allowed(message.chat.id):
            return

        # Проверяем упоминание бота
        if not _is_bot_mentioned(message.text):
            return

        question = _strip_bot_mention(message.text)
        if not question:
            await message.reply("Задай вопрос после упоминания.")
            return
    elif is_private:
        question = message.text
    else:
        return

    try:
        await bot.send_chat_action(message.chat.id, "typing")

        if is_group:
            history = _get_history(message.chat.id)
            answer = await ask_perplexity(
                question,
                system_prompt=GROUP_SYSTEM_PROMPT,
                history=history,
            )
            _add_to_history(message.chat.id, "user", question)
            _add_to_history(message.chat.id, "assistant", answer)
        else:
            answer = await ask_perplexity(question)

        await bot.send_message(
            chat_id=message.chat.id,
            text=answer[:4096],
            reply_to_message_id=message.message_id if is_group else None,
        )
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
    logger.info(f"OWNER_ID={OWNER_ID}")

    allowed = group_manager.get_allowed_ids()
    if allowed:
        logger.info(f"Активные группы: {allowed}")
    else:
        logger.info("Нет активных групп")

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
            "my_chat_member",
            "callback_query",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
