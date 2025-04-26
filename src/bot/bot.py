import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from src.data.manager import DataManager
from src.services.analyzer import OpenAIAnalyzer
from src.config import TELEGRAM_BOT_TOKEN, OPENAI_API_TOKEN, OPENAI_BASE_URL
from .handlers import Handlers

logger = logging.getLogger(__name__)

class ModerationBot:
    def __init__(self):
        self.data_manager = DataManager()
        self.analyzer = OpenAIAnalyzer(
            api_key=OPENAI_API_TOKEN,
            base_url=OPENAI_BASE_URL
        )
        self.analyzer.set_data_manager(self.data_manager)
        self.application = None
        self.handlers = Handlers(self.data_manager, self.analyzer)

    def setup_handlers(self):
        command_handlers = [
            ('start', self.handlers.start),
            ('commands', self.handlers.show_commands),
            ('settings', self.handlers.show_settings),
            ('set_sensitivity', self.handlers.set_sensitivity),
            ('add_ban_word', self.handlers.add_ban_word),
            ('remove_ban_word', self.handlers.remove_ban_word),
            ('ban_list', self.handlers.show_ban_list),
            ('stats', self.handlers.show_stats),
            ('user_info', self.handlers.show_user_info)
        ]

        for cmd, handler in command_handlers:
            self.application.add_handler(CommandHandler(cmd, handler))

        # Обработчик обычных сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.handle_message)
        )
        
        # Обработчик ошибок
        self.application.add_error_handler(self.handlers.error_handler)

    def run(self):
        try:
            self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            self.setup_handlers()
            logger.info("Starting moderation bot...")
            self.application.run_polling()
        except Exception as e:
            logger.critical(f"Bot crashed: {str(e)}", exc_info=True)
        finally:
            logger.info("Bot stopped")