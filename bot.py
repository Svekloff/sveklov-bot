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
    result = text.replace(bot_tag, "").replace(bot_tag.lower(), "").strip()
    return result


def _build_groups_keyboard() -> InlineKeyboardMarkup:
    """Строит инлайн-клавиатуру со списком активных групп."""
    groups = group_manager.list_groups()
    buttons = []
    for gid, info in groups.items():
        label = info.get("title") or str(gid)
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"group_info:{gid}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить группу", callback_data="group_add")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_group_detail_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Строит клавиатуру для управления конкретной группой."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"group_remove:{group_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="group_list")],
    ])


# ─── Handlers ────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "Привет! Я AI-ассистент.\n"
        "• Напишите мне в личку — отвечу.\n"
        "• Упомяните меня в группе — отвечу там.\n"
        "• Подключите бизнес-аккаунт — буду отвечать за вас."
    )


@dp.message(Command("groups"))
async def cmd_groups(message: types.Message) -> None:
    """Показывает список активных групп с инлайн-кнопками."""
    if not _is_owner(message.from_user.id):
        await message.answer("Эта команда доступна только владельцу бота.")
        return
    groups = group_manager.list_groups()
    if not groups:
        text = "Активных групп нет.\nДобавьте бота в группу и он зарегистрируется автоматически."
    else:
        text = f"Активные группы ({len(groups)}):"
    await message.answer(text, reply_markup=_build_groups_keyboard())


@dp.callback_query(F.data == "group_list")
async def cb_group_list(callback: CallbackQuery) -> None:
    """Возврат к списку групп."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    groups = group_manager.list_groups()
    text = f"Активные группы ({len(groups)}):" if groups else "Активных групп нет."
    await callback.message.edit_text(text, reply_markup=_build_groups_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("group_info:"))
async def cb_group_info(callback: CallbackQuery) -> None:
    """Показывает детали группы."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    group_id = int(callback.data.split(":", 1)[1])
    groups = group_manager.list_groups()
    info = groups.get(group_id) or groups.get(str(group_id))
    if not info:
        await callback.answer("Группа не найдена", show_alert=True)
        return
    title = info.get("title") or str(group_id)
    added = info.get("added_at", "неизвестно")
    text = f"📋 <b>{title}</b>\nID: <code>{group_id}</code>\nДобавлена: {added}"
    await callback.message.edit_text(
        text,
        reply_markup=_build_group_detail_keyboard(group_id),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("group_remove:"))
async def cb_group_remove(callback: CallbackQuery) -> None:
    """Удаляет группу из активных."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    group_id = int(callback.data.split(":", 1)[1])
    removed = group_manager.remove_group(group_id)
    if removed:
        await callback.answer("Группа удалена", show_alert=True)
    else:
        await callback.answer("Группа не найдена", show_alert=True)
    # Возврат к списку
    groups = group_manager.list_groups()
    text = f"Активные группы ({len(groups)}):" if groups else "Активных групп нет."
    await callback.message.edit_text(text, reply_markup=_build_groups_keyboard())


@dp.callback_query(F.data == "group_add")
async def cb_group_add(callback: CallbackQuery) -> None:
    """Инструкция по добавлению группы."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(
        "Чтобы добавить группу:\n"
        "1. Добавьте бота в нужную группу\n"
        "2. Дайте боту права администратора\n"
        "3. Группа автоматически появится в списке",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="group_list")]
        ])
    )
    await callback.answer()


@dp.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated) -> None:
    """Обрабатывает добавление/удаление бота в группы."""
    chat = update.chat
    new_status = update.new_chat_member.status
    if chat.type in ("group", "supergroup"):
        if new_status in ("member", "administrator"):
            group_manager.add_group(chat.id, chat.title or str(chat.id))
            logger.info("Bot added to group: %s (%s)", chat.title, chat.id)
        elif new_status in ("left", "kicked"):
            group_manager.remove_group(chat.id)
            logger.info("Bot removed from group: %s (%s)", chat.title, chat.id)


@dp.business_connection()
async def on_business_connection(connection: BusinessConnection) -> None:
    if connection.is_enabled:
        business_connections[connection.user.id] = connection.id
        logger.info("Business connection established: user=%s", connection.user.id)
    else:
        business_connections.pop(connection.user.id, None)
        logger.info("Business connection removed: user=%s", connection.user.id)


@dp.business_message()
async def handle_business_message(message: types.Message) -> None:
    user_id = message.chat.id
    connection_id = business_connections.get(user_id)
    if not connection_id:
        return
    text = message.text or message.caption or ""
    if not text.strip():
        return
    _add_to_history(user_id, "user", text)
    history = _get_history(user_id)
    try:
        reply = await ask_perplexity(text, history=history, system_prompt=BUSINESS_SYSTEM_PROMPT)
    except Exception as e:
        logger.error("Perplexity error: %s", e)
        return
    _add_to_history(user_id, "assistant", reply)
    await bot.send_message(
        chat_id=user_id,
        text=reply,
        business_connection_id=connection_id,
    )


@dp.message(F.chat.type == "private")
async def handle_private_message(message: types.Message) -> None:
    user_id = message.from_user.id
    text = ""

    if message.voice:
        try:
            text = await transcribe_voice(bot, message.voice)
        except Exception as e:
            logger.error("Voice transcription error: %s", e)
            await message.answer("Не удалось распознать голосовое сообщение.")
            return
    elif message.photo:
        caption = message.caption or ""
        try:
            text = await analyze_image(bot, message.photo[-1], caption)
        except Exception as e:
            logger.error("Image analysis error: %s", e)
            await message.answer("Не удалось проанализировать изображение.")
            return
    else:
        text = message.text or ""

    if not text.strip():
        return

    _add_to_history(user_id, "user", text)
    history = _get_history(user_id)
    try:
        reply = await ask_perplexity(text, history=history)
    except Exception as e:
        logger.error("Perplexity error: %s", traceback.format_exc())
        await message.answer("Произошла ошибка при обращении к AI.")
        return
    _add_to_history(user_id, "assistant", reply)
    await message.answer(reply)


@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: types.Message) -> None:
    text = message.text or message.caption or ""
    if not _is_bot_mentioned(text):
        return
    clean_text = _strip_bot_mention(text)
    if not clean_text.strip():
        await message.answer("Чем могу помочь?")
        return
    chat_id = message.chat.id
    _add_to_history(chat_id, "user", clean_text)
    history = _get_history(chat_id)
    try:
        reply = await ask_perplexity(
            clean_text,
            history=history,
            system_prompt=GROUP_SYSTEM_PROMPT,
        )
    except Exception as e:
        logger.error("Perplexity error in group: %s", traceback.format_exc())
        await message.answer("Произошла ошибка при обращении к AI.")
        return
    _add_to_history(chat_id, "assistant", reply)
    await message.answer(reply)


@dp.inline_query()
async def handle_inline(query: InlineQuery) -> None:
    q = query.query.strip()
    if not q:
        await query.answer(
            [],
            switch_pm_text="Введите запрос для поиска",
            switch_pm_parameter="inline_help",
            cache_time=1,
        )
        return
    try:
        answer = await ask_perplexity(q)
    except Exception as e:
        logger.error("Inline query error: %s", e)
        answer = "Ошибка при получении ответа."
    result = InlineQueryResultArticle(
        id="1",
        title=q[:50],
        input_message_content=InputTextMessageContent(message_text=answer),
        description=answer[:100],
    )
    await query.answer([result], cache_time=5)


async def main() -> None:
    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
