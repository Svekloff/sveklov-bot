"""
Gemini API client with Google Search grounding.
Free tier: unlimited tokens + 500 grounded requests/day.
"""

from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, SYSTEM_PROMPT, MAX_TOKENS

_client = genai.Client(api_key=GEMINI_API_KEY)

_grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)


async def ask_ai(question: str) -> str:
    """Send a question to Gemini with Google Search grounding."""
    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[_grounding_tool],
                max_output_tokens=MAX_TOKENS,
            ),
        )

        answer = response.text or "Не удалось получить ответ."

        # Append grounding sources if available
        if (response.candidates
                and response.candidates[0].grounding_metadata
                and response.candidates[0].grounding_metadata.grounding_supports):
            chunks = response.candidates[0].grounding_metadata.grounding_chunks or []
            urls = []
            for chunk in chunks[:5]:
                if hasattr(chunk, "web") and chunk.web:
                    title = chunk.web.title or chunk.web.uri
                    urls.append(f"• {title}: {chunk.web.uri}")
            if urls:
                answer += "\n\n🔗 Источники:\n" + "\n".join(urls)

        return answer

    except Exception as e:
        return f"⚠️ Ошибка при обращении к Gemini API: {e}"
