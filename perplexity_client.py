import aiohttp
import re
from config import PERPLEXITY_API_KEY, PERPLEXITY_MODEL, SYSTEM_PROMPT, MAX_TOKENS

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def clean_citations(text: str) -> str:
    """Убирает сноски вида [1], [2][3] и т.д. из текста."""
    return re.sub(r'\[\d+\]', '', text).strip()


async def ask_perplexity(
    question: str,
    system_prompt: str | None = None,
    history: list[dict] | None = None,
    image_context: str | None = None,
) -> str:
    """Отправляет вопрос в Perplexity API и возвращает ответ.

    Args:
        question: текст текущего вопроса
        system_prompt: кастомный системный промпт (бизнес-режим / группы)
        history: список предыдущих сообщений [{role, content}, ...]
        image_context: описание изображения от vision-модели (для групп)
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
                return f"Ошибка API ({resp.status}): {error_text}"
            data = await resp.json()
            text = data["choices"][0]["message"]["content"]
            # Убираем сноски если используется кастомный промпт
            if system_prompt:
                text = clean_citations(text)
            return text
