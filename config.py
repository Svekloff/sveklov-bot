import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Owner Telegram ID (for admin commands)
try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except ValueError:
    OWNER_ID = 0

# System prompts
BUSINESS_SYSTEM_PROMPT = os.getenv(
    "BUSINESS_SYSTEM_PROMPT",
    "You are a helpful business assistant. Be concise, professional and friendly."
)

GROUP_SYSTEM_PROMPT = os.getenv(
    "GROUP_SYSTEM_PROMPT",
    "You are a helpful assistant in a group chat. Be concise and friendly."
)

# Max conversation history entries (user+assistant pairs)
try:
    MAX_HISTORY = int(os.getenv("MAX_HISTORY", "10"))
except ValueError:
    MAX_HISTORY = 10

# Groups storage file path
GROUPS_FILE = os.getenv("GROUPS_FILE", "groups.json")
