import logging

from services.bot_app import build_bot
from services.config import load_settings
from services.database import close_database
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


def run() -> None:
    setup_logging()

    settings = load_settings()
    # init_database(settings)
    # connect_database()

    bot = build_bot(settings)

    logger.info('Starting bot process...')

    try:
        bot.run(settings.token)
    finally:
        close_database()


if __name__ == '__main__':
    run()
