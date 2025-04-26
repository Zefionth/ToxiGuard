import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_TOKEN = os.getenv('OPENAI_API_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_BASE_URL = "https://api.proxyapi.ru/openai/v1"