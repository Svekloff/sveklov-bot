import aiohttp
import logging
import re
from urllib.parse import urlparse
from config import PERPLEXITY_API_KEY, PERPLEXITY_MODEL, SYSTEM_PROMPT, MAX_TOKENS

logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def clean_citations(text: str) -> str:
    """Убирает сноски вида [1], [2][3] и т.д. из текста."""
    return re.sub(r'\[\d+\]', '', text).strip()


def _domain_name(url: str) -> str:
    """Извлекает короткое имя домена для отображения в ссылке."""
    try:
        host = urlparse(url).hostname or url
        # Убираем www.
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return url


def _inline_citations(text: str, citations: list[str]) -> str:
    """Заменяет сноски [1], [2] на инлайн-ссылки Markdown.

    Пример: 'Текст [1][2]' → 'Текст [habr.com](url) [wiki.org](url)'
    """
    if not citations:
        return clean_citations(text)

    def replace_ref(match: re.Match) -> str:
        idx = int(match.group(1)) - 1  # сноски начинаются с 1
        if 0 <= idx < len(citations):
            url = citations[idx]
            name = _domain_name(url)
            return f" [{name}]({url})"
        return ""

    result = re.sub(r'\[(\d+)\]', replace_ref, text)
    # Убираем двойные пробелы
    result = re.sub(r'  +', ' ', result)
    return result.strip()


def _sanitize_markdown(text: str) -> str:
    """Приводит Markdown к Telegram-совместимому виду.

    Telegram MarkdownV2 капризный, поэтому используем обычный Markdown.
    Убираем неподдерживаемые элементы: заголовки (#), горизонтальные линии.
    Проверяем парность символов форматирования.
    """
    # Убираем заголовки Markdown (### Текст → *Текст*)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
    # Убираем горизонтальные линии
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    # Убираем ** жирный ** → * жирный * (Telegram Markdown v1 не поддерживает **)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    # Убираем __ курсив __ → _ курсив _
    text = re.sub(r'__(.+?)__', r'_\1_', text)
    # Убираем пустые строки подряд (больше 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _ensure_alternating(messages: list[dict]) -> list[dict]:
    """Гарантирует чередование user/assistant после system.

    Perplexity API требует строгое чередование:
    system → user → assistant → user → assistant → ... → user

    Если два подряд одной роли — объединяем текст в одно сообщение.
    Последнее сообщение всегда должно быть user.
    """
    if not messages:
        return messages

    result = [messages[0]]  # system

    for msg in messages[1:]:
        if msg["role"] == "system":
            # Пропускаем лишние system-сообщения
            continue
        if result[-1]["role"] == msg["role"]:
            # Два подряд одной роли — объединяем
            result[-1] = {
                "role": msg["role"],
                "content": result[-1]["content"] + "\n" + msg["content"],
            }
        else:
            result.append(msg)

    # Последнее сообщение должно быть user
    if result[-1]["role"] != "user":
        # Если последнее — assistant, убираем его
        result.pop()

    return result


async def ask_perplexity(
    question: str,
    system_prompt: str | None = None,
    history: list[dict] | None = None,
    image_context: str | None = None,
    format_markdown: bool = False,
) -> str:
    """Отправляет вопрос в Perplexity API и возвращает ответ.

    Args:
        question: текст текущего вопроса
        system_prompt: кастомный системный промпт (бизнес-режим / группы)
        history: список предыдущих сообщений [{role, content}, ...]
        image_context: описание изображения от vision-модели (для групп)
        format_markdown: если True — конвертирует сноски в инлайн-ссылки и приводит к Telegram Markdown
    """
    prompt = system_prompt if system_prompt else SYSTEM_PROMPT

    messages = [{"role": "system", "content": prompt}]

    # Добавляем историю диалога (если есть)
    if history:
        messages.extend(history)

    # Если есть контекст изображения — добавляем его к вопросу
    user_content = question
    if image_context:
        user_content = (
            f"[Собеседник отправил картинку. Описание картинки: {image_context}]\n"
            f"{question if question else 'Прокомментируй эту картинку.'}"
        )

    # Добавляем текущий вопрос
    messages.append({"role": "user", "content": user_content})

    # Валидация: гарантируем чередование user/assistant
    messages = _ensure_alternating(messages)

    logger.debug(f"[perplexity] отправляем {len(messages)} сообщений")

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            PERPLEXITY_API_URL, headers=headers, json=payload
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"[perplexity] ошибка {resp.status}: {error_text}")
                return f"Ошибка API ({resp.status}): {error_text}"
            data = await resp.json()
            text = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])

            if format_markdown:
                # Конвертируем сноски в инлайн-ссылки и приводим Markdown
                text = _inline_citations(text, citations)
                text = _sanitize_markdown(text)
            elif system_prompt:
                # Бизнес-режим — просто убираем сноски
                text = clean_citations(text)

            return text
