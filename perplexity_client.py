import aiohttp
from config import PERPLEXITY_API_KEY, PERPLEXITY_MODEL, SYSTEM_PROMPT, MAX_TOKENS

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


async def ask_perplexity(question: str) -> str:
    """Отправляет вопрос в Perplexity API и возвращает ответ."""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
            return data["choices"][0]["message"]["content"]
