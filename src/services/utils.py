"""
Модуль утилит для бота.
Содержит вспомогательные функции.
"""

import logging


class Logger:
    """Класс для настройки логирования."""

    @staticmethod
    def init_logging() -> None:
        """Инициализирует конфигурацию логирования."""
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO,
            handlers=[
                logging.FileHandler('moderation_bot.log'),
                logging.StreamHandler()
            ]
        )


def init_logging() -> None:
    """Инициализирует логирование (обертка для совместимости)."""
    Logger.init_logging()