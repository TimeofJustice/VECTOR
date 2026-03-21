# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import logging

from services.bot import build
from services.config import load_settings
from services.database import init_database
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


def run() -> None:
    """Main entry point for the application."""
    setup_logging()

    # Load configuration
    settings = load_settings()

    # Initialize database and create tables
    db = init_database(settings)

    # Build and run the bot
    bot = build(settings)
    logger.info("Starting bot process...")
    try:
        bot.run(settings.token)
    finally:
        # Ensure the database connection is closed on shutdown
        db.close()


if __name__ == "__main__":
    run()
