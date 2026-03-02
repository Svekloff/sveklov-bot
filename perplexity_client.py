import aiohttp
import re
from config import PERPLEXITY_API_KEY, PERPLEXITY_MODEL, SYSTEM_PROMPT, MAX_TOKENS

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def clean_citations(text: str) -> str:
    """Убирает сноски вида [1], [2][3] и т.д. из текста."""
    return re.sub(r'\[\d+\]', '', text).strip()


async def ask_perplexity(question: str, system_prompt: str | None = None) -> str:
    """Отправляет вопрос в Perplexity API и возвращает ответ."""
    prompt = system_prompt if system_prompt else SYSTEM_PROMPT

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ],
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
            # Убираем сноски если используется кастомный промпт (бизнес-режим)
            if system_prompt:
                text = clean_citations(text)
            return text
