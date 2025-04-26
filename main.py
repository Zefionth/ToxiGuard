import logging
from src.bot.bot import ModerationBot

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('moderation_bot.log'),
        logging.StreamHandler()
    ]
)

if __name__ == '__main__':
    bot = ModerationBot()
    bot.run()