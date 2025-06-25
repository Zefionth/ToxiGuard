"""
Основной модуль для запуска бота модерации.
Настраивает логирование и запускает бота.
"""

from src.bot.bot import ModerationBot
from src.services.utils import init_logging


def main() -> None:
    """
    Основная функция для запуска бота.
    Инициализирует логирование и запускает бота модерации.
    """
    init_logging()
    bot = ModerationBot()
    bot.run()


if __name__ == '__main__':
    main()