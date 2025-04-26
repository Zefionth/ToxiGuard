import logging

def init_logging():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('moderation_bot.log'),
            logging.StreamHandler()
        ]
    )