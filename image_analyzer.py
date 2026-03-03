import aiohttp
import base64
import logging

from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


async def analyze_image(
    image_bytes: bytes,
    prompt: str,
    system_prompt: str | None = None,
    history: list[dict] | None = None,
) -> str | None:
    """Анализирует изображение через Groq Vision (Llama 4 Scout).

    Args:
        image_bytes: байты изображения (JPEG/PNG)
        prompt: текст запроса к картинке (или пустой — тогда просто "опиши")
        system_prompt: системный промпт
        history: история диалога
    """
    if not GROQ_API_KEY:
        logger.error("[vision] GROQ_API_KEY не задан")
        return None

    # Кодируем картинку в base64 (лимит Groq: 4 MB)
    if len(image_bytes) > 4 * 1024 * 1024:
        logger.warning(f"[vision] изображение слишком большое: {len(image_bytes)} байт")
        return None

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    # Определяем текст запроса
    user_text = prompt if prompt else "Что на этой картинке?"

    # Собираем messages
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Добавляем историю (если есть)
    if history:
        messages.extend(history)

    # Добавляем текущее сообщение с картинкой
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": user_text},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_image}",
                },
            },
        ],
    })

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": VISION_MODEL,
        "messages": messages,
        "max_tokens": 1024,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GROQ_CHAT_URL, headers=headers, json=payload
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"[vision] Groq API ошибка ({resp.status}): {error_text}")
                    return None

                data = await resp.json()
                text = data["choices"][0]["message"]["content"]
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"[vision] ошибка: {e}")
        return None
