import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Ты — умный AI-ассистент в Telegram. Отвечай кратко, по делу и на языке вопроса. "
    "Используй актуальную информацию из интернета. Если есть источники — укажи их.",
)
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "SveklovBot").lower()
