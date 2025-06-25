"""
Модуль конфигурации бота.
Загружает переменные окружения и настройки API.
"""

import os
from dotenv import load_dotenv


class Config:
    """Класс для хранения конфигурации бота."""

    def __init__(self) -> None:
        """Инициализирует конфигурацию, загружая переменные окружения."""
        load_dotenv()
        self.OPENAI_API_TOKEN = os.getenv('OPENAI_API_TOKEN')
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.OPENAI_BASE_URL = "https://api.proxyapi.ru/openai/v1"


config = Config()