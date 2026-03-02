import aiohttp
import logging

from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
WHISPER_MODEL = "whisper-large-v3-turbo"


async def transcribe_voice(audio_bytes: bytes) -> str | None:
    """Отправляет аудио (OGG/Opus) в Groq Whisper и возвращает текст."""
    if not GROQ_API_KEY:
        logger.error("[stt] GROQ_API_KEY не задан")
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }

    form = aiohttp.FormData()
    form.add_field(
        "file",
        audio_bytes,
        filename="voice.ogg",
        content_type="audio/ogg",
    )
    form.add_field("model", WHISPER_MODEL)
    form.add_field("response_format", "json")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            GROQ_TRANSCRIPTION_URL, headers=headers, data=form
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"[stt] Groq API ошибка ({resp.status}): {error_text}")
                return None

            data = await resp.json()
            text = data.get("text", "").strip()
            return text if text else None
