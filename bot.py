"""
Telegram AI Bot — @SveklovBot
Responds to @mentions in group chats and supports inline queries.
Powered by Perplexity Sonar API.
"""

import asyncio
import hashlib
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import TELEGRAM_BOT_TOKEN, BOT_USERNAME
from perplexity_client import ask_perplexity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("sveklov_bot")

router = Router()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_question(text: str, bot_username: str) -> str | None:
    """Extract the question after @bot_username mention. Returns None if no mention."""
    if not text:
        return None

    lower = text.lower()
    mention = f"@{bot_username}"

    if mention not in lower:
        return None

    # Remove the mention and strip whitespace
    idx = lower.index(mention)
    question = (text[:idx] + text[idx + len(mention):]).strip()
    return question if question else None


def _truncate(text: str, limit: int = 4096) -> str:
    """Truncate text to Telegram message limit."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


# ── Handlers ─────────────────────────────────────────────────────────────────

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(
        "👋 Привет! Я AI-бот, работающий на Perplexity Sonar.\n\n"
        "**Как использовать:**\n"
        "• В группе — упомяните @SveklovBot и задайте вопрос\n"
        "• В личке — просто напишите вопрос\n"
        "• В любом чате — наберите `@SveklovBot ваш вопрос` (inline-режим)\n\n"
        "Я ищу актуальную информацию в интернете и генерирую ответ.",
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(F.text.startswith("/help"))
async def handle_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "**Команды:**\n"
        "/start — Приветствие\n"
        "/help  — Эта справка\n\n"
        "**Использование:**\n"
        "• В группе: `@SveklovBot когда следующий запуск SpaceX?`\n"
        "• Inline:   `@SveklovBot курс биткоина`\n"
        "• ЛС:      просто напишите вопрос",
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(F.text)
async def handle_mention(message: Message) -> None:
    """Handle messages that mention the bot in groups or direct messages."""
    text = message.text or ""
    chat_type = message.chat.type

    # In private chats — answer everything
    if chat_type == "private":
        question = text.strip()
    else:
        # In groups — answer only when mentioned
        question = _extract_question(text, BOT_USERNAME)
        if question is None:
            return  # Not for us

    if not question:
        await message.reply("Задайте мне вопрос после @-упоминания.")
        return

    logger.info(
        "Question from %s (chat %s): %s",
        message.from_user.username if message.from_user else "?",
        message.chat.id,
        question[:80],
    )

    # Show "typing…" while Perplexity processes the query
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    answer = await ask_perplexity(question)
    await message.reply(_truncate(answer))


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery) -> None:
    """Handle inline queries — user types @SveklovBot <question> in any chat."""
    query_text = (inline_query.query or "").strip()

    if len(query_text) < 3:
        # Too short — show a hint
        await inline_query.answer(
            results=[],
            cache_time=5,
            switch_pm_text="Введите вопрос (мин. 3 символа)",
            switch_pm_parameter="help",
        )
        return

    logger.info(
        "Inline query from %s: %s",
        inline_query.from_user.username if inline_query.from_user else "?",
        query_text[:80],
    )

    answer = await ask_perplexity(query_text)

    # Generate a deterministic ID for caching
    result_id = hashlib.md5(query_text.encode()).hexdigest()

    results = [
        InlineQueryResultArticle(
            id=result_id,
            title=f"🔍 {query_text[:64]}",
            description=answer[:100] + "..." if len(answer) > 100 else answer,
            input_message_content=InputTextMessageContent(
                message_text=_truncate(answer),
            ),
        )
    ]

    await inline_query.answer(results=results, cache_time=30)


# ── Main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Bot starting…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
