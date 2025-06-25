"""
Основной модуль бота.
Содержит класс ModerationBot и настройку обработчиков команд.
"""

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from src.data.manager import DataManager
from src.services.analyzer import OpenAIAnalyzer
from src.config import config
from .handlers import Handlers


class ModerationBot:
    """Основной класс бота модерации."""

    def __init__(self) -> None:
        """Инициализирует бота с менеджером данных и анализатором."""
        self.data_manager = DataManager()
        self.analyzer = OpenAIAnalyzer(
            api_key=config.OPENAI_API_TOKEN,
            base_url=config.OPENAI_BASE_URL
        )
        self.analyzer.set_data_manager(self.data_manager)
        self.application = None
        self.handlers = Handlers(self.data_manager, self.analyzer)

    def setup_handlers(self) -> None:
        """Настраивает обработчики команд и сообщений."""
        # Основные команды
        self._add_basic_handlers()
        
        # Команды только для групп
        self._add_group_handlers()
        
        # Обработчик обычных сообщений
        self._add_message_handler()
        
        # Обработчик ошибок
        self.application.add_error_handler(self.handlers.error_handler)

    def _add_basic_handlers(self) -> None:
        """Добавляет основные обработчики команд."""
        self.application.add_handler(CommandHandler("start", self.handlers.start))
        self.application.add_handler(CommandHandler("commands", self.handlers.show_commands))

    def _add_group_handlers(self) -> None:
        """Добавляет обработчики команд для групп."""
        group_commands = [
            ('settings', self.handlers.show_settings),
            ('set_sensitivity', self.handlers.set_sensitivity),
            ('add_ban_word', self.handlers.add_ban_word),
            ('remove_ban_word', self.handlers.remove_ban_word),
            ('ban_list', self.handlers.show_ban_list),
            ('stats', self.handlers.show_stats),
            ('user_info', self.handlers.show_user_info)
        ]

        for cmd, handler in group_commands:
            self.application.add_handler(
                CommandHandler(cmd, handler, filters.ChatType.GROUPS)
            )

    def _add_message_handler(self) -> None:
        """Добавляет обработчик текстовых сообщений."""
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
                self.handlers.handle_message
            )
        )

    def run(self) -> None:
        """Запускает бота в режиме опроса."""
        try:
            self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
            self.setup_handlers()
            logging.info("Starting moderation bot...")
            self.application.run_polling()
        except Exception as e:
            logging.critical(f"Bot crashed: {str(e)}", exc_info=True)
        finally:
            logging.info("Bot stopped")