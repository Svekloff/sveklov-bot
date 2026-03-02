"""Perplexity Sonar API client — OpenAI-compatible wrapper."""

from openai import AsyncOpenAI
from config import PERPLEXITY_API_KEY, PERPLEXITY_MODEL, SYSTEM_PROMPT, MAX_TOKENS

_client = AsyncOpenAI(
    api_key=PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai",
)


async def ask_perplexity(question: str) -> str:
    """Send a question to Perplexity Sonar and return the answer with citations."""
    try:
        response = await _client.chat.completions.create(
            model=PERPLEXITY_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            max_tokens=MAX_TOKENS,
        )
        answer = response.choices[0].message.content or "Не удалось получить ответ."

        # Append citations if the API returned them
        citations = getattr(response, "citations", None)
        if citations:
            links = "\n".join(f"• {url}" for url in citations[:5])
            answer += f"\n\n🔗 Источники:\n{links}"

        return answer

    except Exception as e:
        return f"⚠️ Ошибка при обращении к Perplexity API: {e}"
