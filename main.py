import logging
from src.bot.bot import ModerationBot

def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('moderation_bot.log'),
            logging.StreamHandler()
        ]
    )
    bot = ModerationBot()
    bot.run()

if __name__ == '__main__':
    main()  